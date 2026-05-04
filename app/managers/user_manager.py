from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.user import User


def create_user_in_db(
    db: Session,
    *,
    email: str,
    username: str,
    password: str,
    role: str = "buyer",
    email_verified: bool = False,
    must_reset_password: bool = False,
) -> User:
    user = User(
        email=email,
        username=username,
        password=password,
        role=role,
        email_verified=email_verified,
        must_reset_password=must_reset_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_all_users_db(db: Session) -> list[User]:
    return db.query(User).all()


def get_user_by_identifier(db: Session, identifier: str) -> User | None:
    return db.query(User).filter(or_(User.email == identifier, User.username == identifier)).first()


def update_user_role(db: Session, *, user: User, role: str) -> User:
    user.role = role
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_permissions(
    db: Session,
    *,
    user: User,
    permission_grants: str | None,
    permission_revokes: str | None,
) -> User:
    user.permission_grants = permission_grants
    user.permission_revokes = permission_revokes
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_active_session_token(
    db: Session,
    *,
    user: User,
    session_token: str | None,
    session_expires_at: datetime | None,
) -> User:
    user.active_session_token = session_token
    user.active_session_expires_at = session_expires_at
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_password(db: Session, *, user: User, password: str, must_reset_password: bool = False) -> User:
    user.password = password
    user.must_reset_password = must_reset_password
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()


def set_user_email_verified(db: Session, *, user: User, email_verified: bool = True) -> User:
    user.email_verified = email_verified
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_profile_identity(
    db: Session,
    *,
    user: User,
    email: str,
    username: str,
    email_verified: bool,
) -> User:
    user.email = email
    user.username = username
    user.email_verified = email_verified
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
