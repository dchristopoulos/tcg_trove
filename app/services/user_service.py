import hashlib
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    DuplicateEmailError,
    DuplicateUsernameError,
    InvalidPasswordError,
    InvalidRoleError,
    InvalidVerificationTokenError,
)
from app.db.models.user import User
from app.managers.user_manager import (
    create_user_in_db,
    delete_user,
    get_all_users_db,
    get_user_by_email,
    get_user_by_id,
    get_user_by_identifier,
    get_user_by_username,
    set_active_session_token,
    set_user_email_verified,
    update_user_password,
    update_user_permissions,
    update_user_profile_identity,
    update_user_role,
)
from app.schemas.user import ALLOWED_ROLES, UserCreate
from app.services import two_factor_service
from app.services.audit_service import record_audit_event
from app.services.authz_service import ALL_PERMISSIONS
from app.services.two_factor_service import (
    create_challenge,
    verify_challenge,
)
from app.web.auth import hash_password, needs_password_rehash, verify_password

logger = logging.getLogger("tcg_trove.auth")
_COMMON_WEAK_PASSWORDS = {
    "password",
    "password1",
    "qwerty123",
    "12345678",
    "123456789",
    "letmein",
    "admin123",
}
MAX_2FA_VERIFY_ATTEMPTS = two_factor_service.MAX_2FA_VERIFY_ATTEMPTS


def _normalize_identifier(identifier: str) -> str:
    return identifier.strip().lower()


def _email_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret)


def _validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise InvalidPasswordError
    if re.search(r"[A-Za-z]", password) is None:
        raise InvalidPasswordError
    if re.search(r"\d", password) is None:
        raise InvalidPasswordError
    if password.strip().lower() in _COMMON_WEAK_PASSWORDS:
        raise InvalidPasswordError


def register_user(db: Session, user_in: UserCreate) -> User:
    _validate_password_policy(user_in.password)
    if get_user_by_email(db, str(user_in.email)) is not None:
        raise DuplicateEmailError
    if get_user_by_username(db, user_in.username) is not None:
        raise DuplicateUsernameError
    if user_in.role not in ALLOWED_ROLES:
        raise InvalidRoleError
    try:
        return create_user_in_db(
            db,
            email=str(user_in.email),
            username=user_in.username,
            password=hash_password(user_in.password),
            role=user_in.role,
        )
    except IntegrityError as err:
        db.rollback()
        lowered = str(err).lower()
        if "users.email" in lowered or "email" in lowered:
            raise DuplicateEmailError from err
        if "users.username" in lowered or "username" in lowered:
            raise DuplicateUsernameError from err
        raise


def get_user_profile(db: Session, user_id: int) -> User | None:
    return get_user_by_id(db, user_id)


def get_all_users(db: Session) -> list[User]:
    return get_all_users_db(db)


def get_user_by_identifier_use_case(db: Session, identifier: str) -> User | None:
    return get_user_by_identifier(db, identifier)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_identifier(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password):
        return None
    if needs_password_rehash(user.password):
        user = update_user_password(db, user=user, password=hash_password(password), must_reset_password=user.must_reset_password)
    return user


def is_email_verified(user: User) -> bool:
    return bool(getattr(user, "email_verified", False))


def generate_email_verification_token(email: str) -> str:
    return _email_serializer().dumps(email, salt="email-verify")


def verify_email_verification_token(token: str) -> str:
    try:
        return str(
            _email_serializer().loads(
                token,
                salt="email-verify",
                max_age=settings.email_verification_ttl_seconds,
            )
        )
    except (BadSignature, SignatureExpired) as err:
        raise InvalidVerificationTokenError from err


def generate_password_reset_token(email: str, password_hash: str) -> str:
    payload = f"{email}|{password_hash}"
    return _email_serializer().dumps(payload, salt="password-reset")


def verify_password_reset_token(token: str) -> tuple[str, str]:
    try:
        raw = str(
            _email_serializer().loads(
                token,
                salt="password-reset",
                max_age=settings.password_reset_ttl_seconds,
            )
        )
    except (BadSignature, SignatureExpired) as err:
        raise InvalidVerificationTokenError from err
    if "|" not in raw:
        raise InvalidVerificationTokenError
    email, password_hash = raw.split("|", 1)
    return email, password_hash


def mark_user_email_verified(db: Session, *, email: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    return set_user_email_verified(db, user=user, email_verified=True)


def update_own_profile_use_case(db: Session, *, user: User, email: str, username: str) -> tuple[User, bool]:
    new_email = email.strip().lower()
    new_username = username.strip()
    if not new_username:
        raise DuplicateUsernameError

    existing_email = get_user_by_email(db, new_email)
    if existing_email is not None and existing_email.id != user.id:
        raise DuplicateEmailError

    existing_username = get_user_by_username(db, new_username)
    if existing_username is not None and existing_username.id != user.id:
        raise DuplicateUsernameError

    email_changed = new_email != str(user.email)
    updated = update_user_profile_identity(
        db,
        user=user,
        email=new_email,
        username=new_username,
        email_verified=False if email_changed else bool(user.email_verified),
    )
    return updated, email_changed


def change_user_role(db: Session, *, user_id: int, role: str, actor_user_id: int | None = None) -> User | None:
    if role not in ALLOWED_ROLES:
        raise InvalidRoleError
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    updated = update_user_role(db, user=user, role=role)
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="user_role_changed",
        target_type="user",
        target_id=str(updated.id),
        details=f"new_role={role}",
    )
    return updated


def start_two_factor_login(db: Session, *, email: str, password: str) -> tuple[User | None, str | None]:
    user = authenticate_user(db, email, password)
    if user is None:
        return None, None
    challenge_id = secrets.token_urlsafe(16)
    # Demo OTP for local app. Replace with real TOTP/SMS provider in production.
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    create_challenge(
        db,
        challenge_id=challenge_id,
        identifier=_normalize_identifier(str(user.email)),
        otp_code=otp_code,
        ttl_seconds=300,
    )
    logger.info("Issued 2FA challenge", extra={"user": str(user.email), "challenge_id": challenge_id})
    return user, challenge_id


def verify_two_factor_code(db: Session, challenge_id: str, otp_code: str, *, identifier: str) -> bool:
    is_valid = verify_challenge(
        db,
        challenge_id=challenge_id,
        identifier=_normalize_identifier(identifier),
        otp_code=otp_code,
    )
    if not is_valid:
        logger.warning("2FA verification failed", extra={"challenge_id": challenge_id})
    return is_valid


def issue_single_active_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(seconds=max(settings.session_absolute_timeout_seconds, 60))
    set_active_session_token(db, user=user, session_token=token_hash, session_expires_at=expires_at)
    return token


def is_session_token_valid(user: User, session_token: str | None) -> bool:
    if session_token is None:
        return False
    stored_token = user.active_session_token or ""
    if not stored_token:
        return False
    expires_at = getattr(user, "active_session_expires_at", None)
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) >= expires_at:
        return False
    candidate_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    if len(stored_token) == 64:
        return secrets.compare_digest(stored_token, candidate_hash)
    # Backward compatibility for older plaintext tokens while sessions rotate.
    return secrets.compare_digest(stored_token, session_token)


def change_password_use_case(db: Session, *, user: User, new_password: str) -> User:
    _validate_password_policy(new_password)
    return update_user_password(
        db,
        user=user,
        password=hash_password(new_password),
        must_reset_password=False,
    )


def update_user_permissions_use_case(
    db: Session,
    *,
    user_id: int,
    grants: list[str],
    revokes: list[str],
    actor_user_id: int | None,
) -> User | None:
    user = get_user_by_id(db, user_id)
    if user is None:
        return None

    filtered_grants = sorted({perm for perm in grants if perm in ALL_PERMISSIONS})
    filtered_revokes = sorted({perm for perm in revokes if perm in ALL_PERMISSIONS})
    filtered_revokes = [perm for perm in filtered_revokes if perm not in filtered_grants]

    updated = update_user_permissions(
        db,
        user=user,
        permission_grants=",".join(filtered_grants) if filtered_grants else None,
        permission_revokes=",".join(filtered_revokes) if filtered_revokes else None,
    )
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="user_permissions_changed",
        target_type="user",
        target_id=str(updated.id),
        details=f"grants={filtered_grants};revokes={filtered_revokes}",
    )
    return updated


def delete_user_use_case(db: Session, *, user_id: int, actor_user_id: int | None) -> bool:
    user = get_user_by_id(db, user_id)
    if user is None:
        return False
    delete_user(db, user)
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="user_deleted",
        target_type="user",
        target_id=str(user_id),
    )
    return True
