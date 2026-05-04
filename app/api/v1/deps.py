from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDeniedError, UserNotFoundError
from app.db.models.user import User
from app.db.session import get_db
from app.managers.user_manager import get_user_by_id
from app.services.authz_service import has_permission
from app.services.user_service import is_session_token_valid


def get_current_user(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
) -> User:
    if x_user_id is None or x_session_token is None:
        raise PermissionDeniedError
    user = get_user_by_id(db, x_user_id)
    if user is None:
        raise UserNotFoundError
    if not user.active_session_token:
        raise PermissionDeniedError
    if not is_session_token_valid(user, x_session_token):
        raise PermissionDeniedError
    return user


def require_permission(permission: str):
    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(
            current_user.role,
            permission,
            current_user.permission_grants,
            current_user.permission_revokes,
        ):
            raise PermissionDeniedError
        return current_user

    return _checker
