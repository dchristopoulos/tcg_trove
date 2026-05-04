from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models.two_factor_challenge import TwoFactorChallenge

MAX_2FA_VERIFY_ATTEMPTS = 5


def cleanup_expired_challenges(db: Session) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        db.query(TwoFactorChallenge).filter(TwoFactorChallenge.expires_at < now).delete(synchronize_session=False)
        db.commit()
    except OperationalError:
        # Keep auth flow alive even if table migration/init lags behind.
        db.rollback()


def create_challenge(db: Session, *, challenge_id: str, identifier: str, otp_code: str, ttl_seconds: int = 300) -> None:
    cleanup_expired_challenges(db)
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        TwoFactorChallenge(
            challenge_id=challenge_id,
            identifier=identifier,
            otp_code=otp_code,
            expires_at=now + timedelta(seconds=ttl_seconds),
            attempts=0,
            created_at=now,
        )
    )
    db.commit()


def get_challenge_identifier(db: Session, challenge_id: str) -> str | None:
    challenge = db.get(TwoFactorChallenge, challenge_id)
    if challenge is None:
        return None
    return str(challenge.identifier)


def verify_challenge(db: Session, *, challenge_id: str, identifier: str, otp_code: str) -> bool:
    cleanup_expired_challenges(db)
    challenge = db.get(TwoFactorChallenge, challenge_id)
    if challenge is None:
        return False
    challenge_identifier = str(challenge.identifier)
    if challenge_identifier != identifier:
        return False
    raw_attempts = getattr(challenge, "attempts", 0)
    current_attempts = raw_attempts if isinstance(raw_attempts, int) else 0
    if current_attempts >= MAX_2FA_VERIFY_ATTEMPTS:
        db.delete(challenge)
        db.commit()
        return False

    if str(challenge.otp_code) == otp_code:
        db.delete(challenge)
        db.commit()
        return True

    next_attempts = current_attempts + 1
    cast(Any, challenge).attempts = next_attempts
    if next_attempts >= MAX_2FA_VERIFY_ATTEMPTS:
        db.delete(challenge)
    db.commit()
    return False
