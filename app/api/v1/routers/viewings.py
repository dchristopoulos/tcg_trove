from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.viewing import ViewingCreate, ViewingRead
from app.services.viewing_service import (
    create_viewing_use_case,
    listing_viewings_use_case,
    my_viewings_use_case,
)

router = APIRouter(prefix="/viewings", tags=["viewings"])


@router.post("/", response_model=ViewingRead)
def create_viewing_endpoint(
    payload: ViewingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_viewing_use_case(db, user_id=current_user.id, payload=payload)


@router.get("/me", response_model=list[ViewingRead])
def my_viewings_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return my_viewings_use_case(db, user_id=current_user.id)


@router.get("/listing/{listing_id}", response_model=list[ViewingRead])
def listing_viewings_endpoint(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return listing_viewings_use_case(
        db,
        listing_id=listing_id,
        actor_user_id=int(current_user.id),
        actor_role=str(current_user.role),
    )
