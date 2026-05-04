import logging
import secrets
import time
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    DuplicateEmailError,
    DuplicateUsernameError,
    InvalidPasswordError,
    InvalidVerificationTokenError,
)
from app.db.session import get_db
from app.schemas.user import UserCreate
from app.services.email_service import EmailMessage, send_email
from app.services.user_service import (
    authenticate_user,
    generate_email_verification_token,
    get_user_by_identifier_use_case,
    is_email_verified,
    issue_single_active_session,
    mark_user_email_verified,
    register_user,
    verify_email_verification_token,
)
from app.web.auth import (
    SESSION_CSRF_KEY,
    SESSION_LOGIN_AT_KEY,
    SESSION_ROLE_KEY,
    SESSION_TOKEN_KEY,
    SESSION_USER_KEY,
)
from app.web.deps import (
    clear_session,
    get_session_user_id,
    is_rate_limited,
    is_valid_csrf,
    template_response,
)

router = APIRouter()
logger = logging.getLogger("tcg_trove.web.auth")
VERIFICATION_RESEND_AT_KEY = "verification_resend_at"
RESEND_RATE_LIMIT_PER_MINUTE = 6
REGISTER_RATE_LIMIT_PER_MINUTE = 100000


def _send_verification_email(email: str) -> None:
    token = generate_email_verification_token(email)
    verify_url = f"{settings.public_base_url}/verify-email?token={token}"
    send_email(
        EmailMessage(
            to=email,
            subject="Verify your TCG Trove email",
            body=(
                "Welcome to TCG Trove.\n\n"
                f"Verify your email by opening this link:\n{verify_url}\n\n"
                "If you did not register, you can ignore this email."
            ),
        )
    )


def _send_password_reset_email(email: str, reset_token: str) -> None:
    reset_url = f"{settings.public_base_url}/reset-password?token={reset_token}"
    send_email(
        EmailMessage(
            to=email,
            subject="Reset your TCG Trove password",
            body=(
                "We received a request to reset your TCG Trove password.\n\n"
                f"Open this link to continue:\n{reset_url}\n\n"
                "If you did not request this, you can ignore this email."
            ),
        )
    )


def _is_locked_login(request: Request) -> bool:
    locked_until = float(request.session.get("login_locked_until", 0.0))
    if locked_until <= time.time():
        request.session.pop("login_locked_until", None)
        request.session["login_failed_attempts"] = 0
        return False
    return True


def _register_login_failure(request: Request, identifier: str | None = None) -> None:
    attempts = int(request.session.get("login_failed_attempts", 0))
    locked_until = float(request.session.get("login_locked_until", 0.0))
    if locked_until > time.time():
        return
    attempts += 1
    request.session["login_failed_attempts"] = attempts
    if attempts >= settings.login_max_attempts:
        request.session["login_locked_until"] = time.time() + settings.login_lockout_seconds
        logger.warning(
            "Web login locked due to repeated failures",
            extra={
                "ip_address": request.client.host if request.client else "unknown",
                "identifier": (identifier or "unknown").strip().lower(),
                "lockout_seconds": settings.login_lockout_seconds,
            },
        )
        return


def _clear_login_failures(request: Request) -> None:
    request.session["login_failed_attempts"] = 0
    request.session.pop("login_locked_until", None)


def _start_authenticated_session(request: Request, *, user, session_token: str) -> None:
    request.session.clear()
    request.session[SESSION_USER_KEY] = int(user.id)
    request.session[SESSION_TOKEN_KEY] = str(session_token)
    request.session[SESSION_ROLE_KEY] = str(user.role)
    request.session[SESSION_LOGIN_AT_KEY] = int(time.time())
    request.session[SESSION_CSRF_KEY] = secrets.token_urlsafe(24)


@router.get("/users/register", response_class=HTMLResponse)
def register_user_form(request: Request):
    if get_session_user_id(request) is not None:
        return RedirectResponse(url="/dashboard", status_code=303)
    return template_response(request, "register.html", {"error": None})


@router.post("/users/register")
def register_user_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if is_rate_limited(db, request, "register_web", email, REGISTER_RATE_LIMIT_PER_MINUTE):
        return template_response(
            request,
            "register.html",
            {"error": "Too many registration attempts. Try again in a minute."},
            status_code=429,
        )
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    try:
        user = register_user(db, UserCreate(email=email, username=username, password=password))
        background_tasks.add_task(_send_verification_email, str(user.email))
        _start_authenticated_session(
            request,
            user=user,
            session_token=issue_single_active_session(db, user),
        )
        return RedirectResponse(
            url=f"/dashboard?message={quote('Account created. You are signed in. Verify your email when ready from Account settings.')}",
            status_code=303,
        )
    except InvalidPasswordError:
        return template_response(
            request,
            "register.html",
            {"error": "Password must be at least 8 characters and include letters and numbers."},
            status_code=400,
        )
    except (DuplicateEmailError, DuplicateUsernameError):
        return template_response(
            request,
            "register.html",
            {"error": "Email or username already exists"},
            status_code=400,
        )


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, message: str | None = None):
    if get_session_user_id(request) is not None:
        return RedirectResponse(url="/dashboard", status_code=303)
    return template_response(
        request,
        "login.html",
        {
            "error": None,
            "message": message,
            "unverified_identifier": None,
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    csrf_token: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if is_rate_limited(db, request, "login", email, settings.login_rate_limit_per_minute):
        return template_response(
            request,
            "login.html",
            {
                "error": "Too many login attempts. Try again shortly.",
                "message": None,
                "unverified_identifier": None,
            },
            status_code=429,
        )
    if _is_locked_login(request):
        return template_response(
            request,
            "login.html",
            {
                "error": f"Too many attempts. Try again in {settings.login_lockout_seconds} seconds.",
                "message": None,
                "unverified_identifier": None,
            },
            status_code=429,
        )
    user = authenticate_user(db, email, password)
    if user is None:
        _register_login_failure(request, email)
        if _is_locked_login(request):
            return template_response(
                request,
                "login.html",
                {
                    "error": f"Too many attempts. Try again in {settings.login_lockout_seconds} seconds.",
                    "message": None,
                    "unverified_identifier": None,
                },
                status_code=429,
            )
        return template_response(
            request,
            "login.html",
            {"error": "Invalid credentials", "message": None, "unverified_identifier": None},
            status_code=400,
        )
    if not is_email_verified(user):
        return template_response(
            request,
            "login.html",
            {
                "error": "Please verify your email first. Check your inbox for the verification link.",
                "message": None,
                "unverified_identifier": str(user.email),
            },
            status_code=403,
        )
    _clear_login_failures(request)
    _start_authenticated_session(
        request,
        user=user,
        session_token=issue_single_active_session(db, user),
    )
    if user.role == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    if bool(getattr(user, "must_reset_password", False)):
        return RedirectResponse(url="/change-password", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    try:
        email = verify_email_verification_token(token)
    except InvalidVerificationTokenError:
        return template_response(
            request,
            "login.html",
            {
                "error": "Verification link is invalid or expired.",
                "message": None,
                "unverified_identifier": None,
            },
            status_code=400,
        )
    user = mark_user_email_verified(db, email=email)
    if user is None:
        return template_response(
            request,
            "login.html",
            {
                "error": "Account not found for this verification link.",
                "message": None,
                "unverified_identifier": None,
            },
            status_code=404,
        )
    return template_response(
        request,
        "login.html",
        {
            "error": None,
            "message": "Email verified successfully. You can now sign in.",
            "unverified_identifier": None,
        },
    )


@router.post("/resend-verification")
def resend_verification_email(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(...),
    identifier: str = Form(...),
    db: Session = Depends(get_db),
):
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if is_rate_limited(db, request, "resend_verify", identifier, RESEND_RATE_LIMIT_PER_MINUTE):
        return RedirectResponse(
            url=f"/login?message={quote('Too many verification requests. Please wait one minute and try again.')}",
            status_code=303,
        )

    now = int(time.time())
    resend_at = int(request.session.get(VERIFICATION_RESEND_AT_KEY, 0))
    if resend_at > now:
        wait_seconds = resend_at - now
        return RedirectResponse(
            url=f"/login?message={quote(f'Please wait {wait_seconds} seconds before requesting another verification email.')}",
            status_code=303,
        )

    account = get_user_by_identifier_use_case(db, identifier) if identifier else None
    if account is not None and not is_email_verified(account):
        background_tasks.add_task(_send_verification_email, str(account.email))
        request.session[VERIFICATION_RESEND_AT_KEY] = now + settings.email_verification_resend_cooldown_seconds

    return RedirectResponse(
        url=f"/login?message={quote('If the account exists and is not verified, a new verification link has been sent.')}",
        status_code=303,
    )


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    clear_session(request)
    return RedirectResponse(url="/", status_code=303)
