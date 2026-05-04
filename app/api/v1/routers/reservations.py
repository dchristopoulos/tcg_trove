from typing import Any, cast

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.reservation import ReservationCreate, ReservationRead, ReservationStatusUpdate
from app.services.reservation_service import (
    create_reservation_use_case,
    listing_reservations_use_case,
    my_reservations_use_case,
    update_reservation_status_use_case,
)

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("/", response_model=ReservationRead)
def create_reservation_endpoint(
    payload: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_reservation_use_case(db, user_id=int(cast(Any, current_user.id)), payload=payload)


@router.get("/me", response_model=list[ReservationRead])
def my_reservations_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return my_reservations_use_case(db, user_id=int(cast(Any, current_user.id)))


@router.get("/listing/{listing_id}", response_model=list[ReservationRead])
def listing_reservations_endpoint(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return listing_reservations_use_case(
        db,
        listing_id=listing_id,
        actor_user_id=int(cast(Any, current_user.id)),
        actor_role=str(cast(Any, current_user.role)),
    )


@router.put("/{reservation_id}", response_model=ReservationRead)
def update_reservation_status_endpoint(
    reservation_id: int,
    payload: ReservationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_reservation_status_use_case(
        db,
        reservation_id=reservation_id,
        status=payload.status,
        actor_user_id=int(cast(Any, current_user.id)),
        actor_role=str(cast(Any, current_user.role)),
    )
