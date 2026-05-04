from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.favorite import FavoriteRead
from app.services.favorite_service import add_favorite, list_favorites, remove_favorite

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("/", response_model=list[FavoriteRead])
def my_favorites_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_favorites(db, user_id=current_user.id)


@router.post("/{listing_id}", response_model=FavoriteRead)
def add_favorite_endpoint(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return add_favorite(db, user_id=current_user.id, listing_id=listing_id)


@router.delete("/{listing_id}")
def remove_favorite_endpoint(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    remove_favorite(db, user_id=current_user.id, listing_id=listing_id)
    return {"detail": "Favorite removed"}
