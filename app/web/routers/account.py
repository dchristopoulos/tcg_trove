import time
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    DuplicateEmailError,
    DuplicateUsernameError,
    InvalidPasswordError,
    InvalidVerificationTokenError,
)
from app.db.models.audit_log import AuditLog
from app.db.session import get_db
from app.services.audit_service import record_audit_event
from app.services.email_service import EmailMessage, send_email
from app.services.user_service import (
    change_password_use_case,
    generate_email_verification_token,
    generate_password_reset_token,
    get_user_by_identifier_use_case,
    get_user_profile,
    is_email_verified,
    issue_single_active_session,
    mark_user_email_verified,
    update_own_profile_use_case,
    verify_password_reset_token,
)
from app.web.auth import (
    SESSION_LOGIN_AT_KEY,
    SESSION_TOKEN_KEY,
    verify_password,
)
from app.web.deps import (
    get_session_user_id,
    is_rate_limited,
    is_valid_active_session,
    is_valid_csrf,
    request_audit_context,
    template_response,
)

router = APIRouter()
VERIFICATION_RESEND_AT_KEY = "verification_resend_at"
RESEND_RATE_LIMIT_PER_MINUTE = 6


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


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return template_response(request, "forgot_password.html", {"message": None, "error": None})


@router.post("/forgot-password")
def forgot_password_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(...),
    identifier: str = Form(...),
    db: Session = Depends(get_db),
):
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if is_rate_limited(db, request, "forgot_password", identifier, RESEND_RATE_LIMIT_PER_MINUTE):
        return template_response(
            request,
            "forgot_password.html",
            {
                "error": "Too many reset requests. Please wait a minute and try again.",
                "message": None,
            },
            status_code=429,
        )

    user = get_user_by_identifier_use_case(db, identifier) if identifier else None
    if user is not None:
        token = generate_password_reset_token(str(user.email), str(user.password))
        background_tasks.add_task(_send_password_reset_email, str(user.email), token)

    return template_response(
        request,
        "forgot_password.html",
        {
            "error": None,
            "message": "If the account exists, a password reset link has been sent.",
        },
    )


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str | None = None):
    if not token:
        return template_response(
            request,
            "forgot_password.html",
            {"error": "Reset token is missing.", "message": None},
            status_code=400,
        )
    return template_response(
        request,
        "reset_password.html",
        {"error": None, "token": token, "message": None},
    )


@router.post("/reset-password")
def reset_password_submit(
    request: Request,
    csrf_token: str = Form(...),
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if len(new_password) < 8:
        return template_response(
            request,
            "reset_password.html",
            {"error": "New password must be at least 8 characters.", "token": token, "message": None},
            status_code=400,
        )
    if new_password != confirm_password:
        return template_response(
            request,
            "reset_password.html",
            {"error": "Password confirmation does not match.", "token": token, "message": None},
            status_code=400,
        )

    try:
        email, token_password_hash = verify_password_reset_token(token)
    except InvalidVerificationTokenError:
        return template_response(
            request,
            "forgot_password.html",
            {"error": "Reset link is invalid or expired.", "message": None},
            status_code=400,
        )

    user = get_user_by_identifier_use_case(db, email)
    if user is None or str(user.password) != token_password_hash:
        return template_response(
            request,
            "forgot_password.html",
            {"error": "Reset link is no longer valid. Request a new one.", "message": None},
            status_code=400,
        )

    try:
        change_password_use_case(db, user=user, new_password=new_password)
    except InvalidPasswordError:
        return template_response(
            request,
            "reset_password.html",
            {
                "error": "Password must be at least 8 characters and include letters and numbers.",
                "token": token,
                "message": None,
            },
            status_code=400,
        )
    return RedirectResponse(
        url=f"/login?message={quote('Password reset successful. Please sign in with your new password.')}",
        status_code=303,
    )


@router.get("/change-password", response_class=HTMLResponse)
def change_password_form(request: Request, db: Session = Depends(get_db)):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    return template_response(request, "change_password.html", {"error": None})


@router.get("/account", response_class=HTMLResponse)
def account_settings(request: Request, db: Session = Depends(get_db), message: str | None = None):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    activity = (
        db.query(AuditLog)
        .filter(AuditLog.actor_user_id == user.id)
        .order_by(desc(AuditLog.created_at))
        .limit(8)
        .all()
    )
    return template_response(
        request,
        "account.html",
        {
            "user": user,
            "message": message,
            "error": None,
            "activity": activity,
        },
    )


@router.post("/account/profile")
def update_own_profile(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")

    try:
        updated, email_changed = update_own_profile_use_case(
            db,
            user=user,
            email=email,
            username=username,
        )
    except (DuplicateEmailError, DuplicateUsernameError):
        return template_response(
            request,
            "account.html",
            {
                "user": user,
                "message": None,
                "error": "Email or username is already in use.",
                "activity": (
                    db.query(AuditLog)
                    .filter(AuditLog.actor_user_id == user.id)
                    .order_by(desc(AuditLog.created_at))
                    .limit(8)
                    .all()
                ),
            },
            status_code=400,
        )

    if email_changed:
        record_audit_event(
            db,
            actor_user_id=updated.id,
            action="account_profile_updated",
            target_type="user",
            target_id=str(updated.id),
            details="email_changed=true",
            **request_audit_context(request),
        )
        background_tasks.add_task(_send_verification_email, str(updated.email))
        return RedirectResponse(
            url=f"/account?message={quote('Profile updated. Please verify your new email address.')}",
            status_code=303,
        )
    record_audit_event(
        db,
        actor_user_id=updated.id,
        action="account_profile_updated",
        target_type="user",
        target_id=str(updated.id),
        details="email_changed=false",
        **request_audit_context(request),
    )
    return RedirectResponse(
        url=f"/account?message={quote('Profile updated successfully.')}",
        status_code=303,
    )


@router.post("/account/resend-verification")
def resend_verification_from_account(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")

    now = int(time.time())
    resend_at = int(request.session.get(VERIFICATION_RESEND_AT_KEY, 0))
    if resend_at > now:
        wait_seconds = resend_at - now
        return RedirectResponse(
            url=f"/account?message={quote(f'Please wait {wait_seconds} seconds before requesting another verification email.')}",
            status_code=303,
        )
    if is_email_verified(user):
        return RedirectResponse(
            url=f"/account?message={quote('Your email is already verified.')}",
            status_code=303,
        )

    background_tasks.add_task(_send_verification_email, str(user.email))
    request.session[VERIFICATION_RESEND_AT_KEY] = now + settings.email_verification_resend_cooldown_seconds
    record_audit_event(
        db,
        actor_user_id=user.id,
        action="account_resend_verification",
        target_type="user",
        target_id=str(user.id),
        **request_audit_context(request),
    )
    return RedirectResponse(
        url=f"/account?message={quote('Verification email sent. Check your inbox.')}",
        status_code=303,
    )


@router.post("/change-password")
def change_password_submit(
    request: Request,
    csrf_token: str = Form(...),
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if not verify_password(current_password, user.password):
        return template_response(
            request,
            "change_password.html",
            {"error": "Current password is invalid."},
            status_code=400,
        )
    if len(new_password) < 8:
        return template_response(
            request,
            "change_password.html",
            {"error": "New password must be at least 8 characters."},
            status_code=400,
        )
    if new_password != confirm_password:
        return template_response(
            request,
            "change_password.html",
            {"error": "New password and confirmation do not match."},
            status_code=400,
        )
    try:
        change_password_use_case(db, user=user, new_password=new_password)
    except InvalidPasswordError:
        return template_response(
            request,
            "change_password.html",
            {"error": "Password must be at least 8 characters and include letters and numbers."},
            status_code=400,
        )
    request.session[SESSION_TOKEN_KEY] = issue_single_active_session(db, user)
    request.session[SESSION_LOGIN_AT_KEY] = int(time.time())
    record_audit_event(
        db,
        actor_user_id=user.id,
        action="account_password_changed",
        target_type="user",
        target_id=str(user.id),
        **request_audit_context(request),
    )
    return RedirectResponse(url="/account", status_code=303)
