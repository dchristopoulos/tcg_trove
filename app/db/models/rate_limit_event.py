from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.base import Base


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"

    id = Column(Integer, primary_key=True, index=True)
    scope_key = Column(String, nullable=False, index=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        index=True,
    )
