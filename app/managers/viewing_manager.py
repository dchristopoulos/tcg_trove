from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy.orm import Session

from app.db.models.viewing import Viewing


def create_viewing(
    db: Session,
    *,
    user_id: int,
    listing_id: int,
    scheduled_at: datetime,
    duration_minutes: int,
    notes: str | None,
) -> Viewing:
    viewing = Viewing(
        user_id=user_id,
        listing_id=listing_id,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        notes=notes,
    )
    db.add(viewing)
    db.commit()
    db.refresh(viewing)
    return viewing


def list_viewings_for_user(db: Session, user_id: int) -> list[Viewing]:
    return db.query(Viewing).filter(Viewing.user_id == user_id).all()


def list_viewings_for_listing(db: Session, listing_id: int) -> list[Viewing]:
    return db.query(Viewing).filter(Viewing.listing_id == listing_id).all()


def has_viewing_conflict(db: Session, *, listing_id: int, scheduled_at: datetime, duration_minutes: int) -> bool:
    candidates = list_viewings_for_listing(db, listing_id)
    new_end = scheduled_at + timedelta(minutes=duration_minutes)
    for item in candidates:
        existing_start = cast(datetime, cast(Any, item.scheduled_at))
        existing_duration = int(cast(Any, item.duration_minutes))
        existing_end = existing_start + timedelta(minutes=existing_duration)
        if scheduled_at < existing_end and existing_start < new_end:
            return True
    return False
