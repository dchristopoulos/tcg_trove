from sqlalchemy.orm import Session

from app.core.exceptions import ListingNotFoundError, PermissionDeniedError, ViewingConflictError
from app.db.models.listing import Listing
from app.db.models.viewing import Viewing
from app.managers.listing_manager import get_listing_by_id
from app.managers.user_manager import get_user_by_id
from app.managers.viewing_manager import (
    create_viewing,
    has_viewing_conflict,
    list_viewings_for_listing,
    list_viewings_for_user,
)
from app.schemas.viewing import ViewingCreate
from app.services.email_service import send_confirmation_email


def create_viewing_use_case(db: Session, *, user_id: int, payload: ViewingCreate) -> Viewing:
    listing_query = db.query(Listing).filter(Listing.id == payload.listing_id)
    if db.get_bind().dialect.name != "sqlite":
        listing_query = listing_query.with_for_update()
    if listing_query.first() is None:
        raise ListingNotFoundError
    if has_viewing_conflict(
        db,
        listing_id=payload.listing_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
    ):
        raise ViewingConflictError
    viewing = create_viewing(
        db,
        user_id=user_id,
        listing_id=payload.listing_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
    )
    user = get_user_by_id(db, user_id)
    if user is not None:
        send_confirmation_email(
            to=str(user.email),
            event_name="Viewing scheduled",
            details=f"Viewing #{viewing.id} is scheduled at {viewing.scheduled_at}.",
        )
    return viewing


def my_viewings_use_case(db: Session, *, user_id: int) -> list[Viewing]:
    return list_viewings_for_user(db, user_id)


def listing_viewings_use_case(
    db: Session,
    *,
    listing_id: int,
    actor_user_id: int,
    actor_role: str,
) -> list[Viewing]:
    listing = get_listing_by_id(db, listing_id)
    if listing is None:
        raise ListingNotFoundError
    if actor_role != "admin" and actor_user_id != int(listing.seller_id):
        raise PermissionDeniedError
    return list_viewings_for_listing(db, listing_id)
