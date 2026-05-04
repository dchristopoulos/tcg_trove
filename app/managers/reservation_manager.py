from datetime import date
from typing import Any, cast

from sqlalchemy.orm import Session

from app.db.models.reservation import Reservation
from app.schemas.status import ReservationStatus

ACTIVE_RESERVATION_STATUSES = {ReservationStatus.PENDING.value, ReservationStatus.CONFIRMED.value}


def create_reservation(
    db: Session,
    *,
    user_id: int,
    listing_id: int,
    start_date: date,
    end_date: date,
    total_price: int,
) -> Reservation:
    reservation = Reservation(
        user_id=user_id,
        listing_id=listing_id,
        start_date=start_date,
        end_date=end_date,
        total_price=total_price,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def list_reservations_for_user(db: Session, user_id: int) -> list[Reservation]:
    return db.query(Reservation).filter(Reservation.user_id == user_id).all()


def list_reservations_for_listing(db: Session, listing_id: int) -> list[Reservation]:
    return db.query(Reservation).filter(Reservation.listing_id == listing_id).all()


def get_reservation_by_id(db: Session, reservation_id: int) -> Reservation | None:
    return db.query(Reservation).filter(Reservation.id == reservation_id).first()


def update_reservation_status(db: Session, reservation: Reservation, *, status: ReservationStatus) -> Reservation:
    reservation.status = cast(Any, status.value)
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def has_reservation_conflict(db: Session, *, listing_id: int, start_date: date, end_date: date) -> bool:
    items = db.query(Reservation).filter(
        Reservation.listing_id == listing_id,
        Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
    ).all()
    for item in items:
        item_start = cast(date, cast(Any, item.start_date))
        item_end = cast(date, cast(Any, item.end_date))
        if start_date <= item_end and item_start <= end_date:
            return True
    return False
