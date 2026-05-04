from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.base import Base


class TwoFactorChallenge(Base):
    __tablename__ = "two_factor_challenges"

    challenge_id = Column(String, primary_key=True, index=True)
    identifier = Column(String, nullable=False, index=True)
    otp_code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC).replace(tzinfo=None))
