import logging
from datetime import date
from typing import Any, cast

from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidDateRangeError,
    InvalidStatusTransitionError,
    ListingNotFoundError,
    PermissionDeniedError,
    ReservationConflictError,
    ReservationNotFoundError,
)
from app.db.models.listing import Listing
from app.db.models.reservation import Reservation
from app.managers.listing_manager import get_listing_by_id
from app.managers.reservation_manager import (
    create_reservation,
    get_reservation_by_id,
    has_reservation_conflict,
    list_reservations_for_listing,
    list_reservations_for_user,
    update_reservation_status,
)
from app.managers.user_manager import get_user_by_id
from app.schemas.reservation import ReservationCreate
from app.schemas.status import ALLOWED_RESERVATION_TRANSITIONS, ReservationStatus
from app.services.audit_service import record_audit_event
from app.services.email_service import send_confirmation_email

logger = logging.getLogger("tcg_trove.reservations")


def _calculate_total_price(price_per_day: int, start_date: date, end_date: date) -> int:
    day_count = (end_date - start_date).days + 1
    return max(day_count, 1) * price_per_day


def create_reservation_use_case(db: Session, *, user_id: int, payload: ReservationCreate) -> Reservation:
    if payload.end_date < payload.start_date:
        raise InvalidDateRangeError
    listing_query = db.query(Listing).filter(Listing.id == payload.listing_id)
    if db.get_bind().dialect.name != "sqlite":
        listing_query = listing_query.with_for_update()
    listing = listing_query.first()
    if listing is None:
        raise ListingNotFoundError
    if user_id == int(cast(Any, listing.seller_id)):
        raise PermissionDeniedError
    if has_reservation_conflict(
        db,
        listing_id=payload.listing_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    ):
        raise ReservationConflictError
    total_price = _calculate_total_price(int(cast(Any, listing.price)), payload.start_date, payload.end_date)
    reservation = create_reservation(
        db,
        user_id=user_id,
        listing_id=payload.listing_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_price=total_price,
    )
    user = get_user_by_id(db, user_id)
    if user is not None:
        try:
            send_confirmation_email(
                to=str(user.email),
                event_name="Reservation created",
                details=f"Reservation #{reservation.id} total is ${reservation.total_price}.",
            )
        except Exception:
            logger.exception("Failed to enqueue reservation confirmation email", extra={"reservation_id": reservation.id})
    try:
        record_audit_event(
            db,
            actor_user_id=user_id,
            action="reservation_created",
            target_type="reservation",
            target_id=str(reservation.id),
            details=f"listing_id={payload.listing_id}",
        )
    except Exception:
        logger.exception("Failed to record reservation audit event", extra={"reservation_id": reservation.id})
    return reservation


def my_reservations_use_case(db: Session, *, user_id: int) -> list[Reservation]:
    return list_reservations_for_user(db, user_id)


def listing_reservations_use_case(
    db: Session,
    *,
    listing_id: int,
    actor_user_id: int,
    actor_role: str,
) -> list[Reservation]:
    listing = get_listing_by_id(db, listing_id)
    if listing is None:
        raise ListingNotFoundError
    if actor_role != "admin" and actor_user_id != int(cast(Any, listing.seller_id)):
        raise PermissionDeniedError
    return list_reservations_for_listing(db, listing_id)


def update_reservation_status_use_case(
    db: Session,
    *,
    reservation_id: int,
    status: ReservationStatus | str,
    actor_user_id: int,
    actor_role: str,
) -> Reservation:
    reservation = get_reservation_by_id(db, reservation_id)
    if reservation is None:
        raise ReservationNotFoundError
    listing = get_listing_by_id(db, int(cast(Any, reservation.listing_id)))
    if listing is None:
        raise ListingNotFoundError
    if actor_role != "admin" and actor_user_id != int(cast(Any, listing.seller_id)):
        raise PermissionDeniedError
    try:
        requested_status = status if isinstance(status, ReservationStatus) else ReservationStatus(str(status))
        current_status = ReservationStatus(str(cast(Any, reservation.status)))
    except ValueError as err:
        raise InvalidStatusTransitionError from err
    if requested_status != current_status and requested_status not in ALLOWED_RESERVATION_TRANSITIONS[current_status]:
        raise InvalidStatusTransitionError
    updated = update_reservation_status(db, reservation, status=requested_status)
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="reservation_status_changed",
        target_type="reservation",
        target_id=str(updated.id),
        details=f"status={requested_status.value}",
    )
    return updated
