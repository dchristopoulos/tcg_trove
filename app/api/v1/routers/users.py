from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_permission
from app.core.exceptions import EmailNotVerifiedError, PermissionDeniedError, UserNotFoundError
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import UserCreate, UserPermissionUpdate, UserRead
from app.services.two_factor_service import get_challenge_identifier
from app.services.user_service import (
    authenticate_user,
    change_password_use_case,
    change_user_role,
    delete_user_use_case,
    get_all_users,
    get_user_by_identifier_use_case,
    get_user_profile,
    is_email_verified,
    issue_single_active_session,
    register_user,
    start_two_factor_login,
    update_user_permissions_use_case,
    verify_two_factor_code,
)

router = APIRouter(prefix="/users", tags=["users"])
_SELF_LOCKOUT_PROTECTED_PERMISSIONS = {"manage_users", "manage_permissions", "delete_users"}


class LoginInitRequest(BaseModel):
    identifier: str | None = None
    email: EmailStr | None = None
    password: str

    @model_validator(mode="after")
    def normalize_identifier(self):
        if not self.identifier:
            self.identifier = str(self.email) if self.email is not None else None
        return self


class LoginInitResponse(BaseModel):
    challenge_id: str
    detail: str


class LoginVerifyRequest(BaseModel):
    email: str | None = None
    password: str | None = None
    challenge_id: str = Field(min_length=10, max_length=256)
    otp_code: str = Field(pattern=r"^\d{6}$")


class LoginVerifyResponse(BaseModel):
    user_id: int
    session_token: str


class RoleUpdateRequest(BaseModel):
    role: str = Field(pattern=r"^(buyer|seller|supervisor|admin)$")


class PasswordUpdateRequest(BaseModel):
    new_password: str = Field(min_length=8)


@router.get("/me", response_model=UserRead)
def get_current_user_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user's profile."""
    return current_user


@router.post("/", response_model=UserRead)
def create_user_endpoint(user_in: UserCreate, db: Session = Depends(get_db)):
    if user_in.role != "buyer":
        raise PermissionDeniedError
    return register_user(db, user_in)


@router.get("/{user_id}", response_model=UserRead)
def get_user_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_permission("manage_users")),
):
    user = get_user_profile(db, user_id)
    if user is None:
        raise UserNotFoundError
    return user


@router.get("/", response_model=list[UserRead])
def get_all_users_endpoint(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_permission("manage_users")),
):
    return get_all_users(db)


@router.post("/login-init", response_model=LoginInitResponse)
def login_init_endpoint(payload: LoginInitRequest, db: Session = Depends(get_db)):
    if not payload.identifier:
        raise UserNotFoundError
    user = get_user_by_identifier_use_case(db, payload.identifier)
    if user is None:
        raise UserNotFoundError
    _, challenge_id = start_two_factor_login(db, email=str(user.email), password=payload.password)
    if challenge_id is None:
        raise UserNotFoundError
    return LoginInitResponse(challenge_id=challenge_id, detail="OTP emitted to server logs for demo")


@router.post("/login-verify", response_model=LoginVerifyResponse)
def login_verify_endpoint(payload: LoginVerifyRequest, db: Session = Depends(get_db)):
    identifier = get_challenge_identifier(db, payload.challenge_id)
    if identifier is None:
        raise UserNotFoundError
    if payload.email and payload.email.strip().lower() != identifier.strip().lower():
        raise UserNotFoundError
    if not verify_two_factor_code(db, payload.challenge_id, payload.otp_code, identifier=identifier):
        raise UserNotFoundError
    user = get_user_by_identifier_use_case(db, identifier)
    if user is None:
        raise UserNotFoundError
    if not is_email_verified(user):
        raise EmailNotVerifiedError
    session_token = issue_single_active_session(db, user)
    return LoginVerifyResponse(user_id=user.id, session_token=session_token)


@router.put("/{user_id}/role", response_model=UserRead)
def update_user_role_endpoint(
    user_id: int,
    payload: RoleUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_permission("manage_users")),
):
    if admin_user.id == user_id and payload.role != "admin":
        raise PermissionDeniedError
    updated = change_user_role(
        db,
        user_id=user_id,
        role=payload.role,
        actor_user_id=admin_user.id,
    )
    if updated is None:
        raise UserNotFoundError
    return updated


@router.put("/{user_id}/password", response_model=UserRead)
def update_user_password_endpoint(
    user_id: int,
    payload: PasswordUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_user_profile(db, user_id)
    if user is None:
        raise UserNotFoundError
    if current_user.role != "admin" and current_user.id != user.id:
        raise PermissionDeniedError
    return change_password_use_case(db, user=user, new_password=payload.new_password)


@router.put("/{user_id}/permissions", response_model=UserRead)
def update_user_permissions_endpoint(
    user_id: int,
    payload: UserPermissionUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_permission("manage_permissions")),
):
    if admin_user.id == user_id and _SELF_LOCKOUT_PROTECTED_PERMISSIONS.intersection(payload.revokes):
        raise PermissionDeniedError
    updated = update_user_permissions_use_case(
        db,
        user_id=user_id,
        grants=payload.grants,
        revokes=payload.revokes,
        actor_user_id=admin_user.id,
    )
    if updated is None:
        raise UserNotFoundError
    return updated


@router.delete("/{user_id}")
def delete_user_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_permission("delete_users")),
):
    if admin_user.id == user_id:
        raise PermissionDeniedError
    removed = delete_user_use_case(db, user_id=user_id, actor_user_id=admin_user.id)
    if not removed:
        raise UserNotFoundError
    return {"detail": "User removed"}
