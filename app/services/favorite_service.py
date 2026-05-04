from sqlalchemy.orm import Session

from app.core.exceptions import FavoriteNotFoundError, ListingNotFoundError
from app.db.models.favorite import Favorite
from app.managers.favorite_manager import (
    create_favorite,
    delete_favorite,
    get_all_favorites,
    get_favorite,
    get_user_favorites,
)
from app.managers.listing_manager import get_listing_by_id


def add_favorite(db: Session, *, user_id: int, listing_id: int) -> Favorite:
    if get_listing_by_id(db, listing_id) is None:
        raise ListingNotFoundError
    existing = get_favorite(db, user_id, listing_id)
    if existing is not None:
        return existing
    return create_favorite(db, user_id, listing_id)


def remove_favorite(db: Session, *, user_id: int, listing_id: int) -> None:
    existing = get_favorite(db, user_id, listing_id)
    if existing is None:
        raise FavoriteNotFoundError
    delete_favorite(db, existing)


def list_favorites(db: Session, *, user_id: int) -> list[Favorite]:
    return get_user_favorites(db, user_id)


def all_favorites_use_case(db: Session) -> list[Favorite]:
    return get_all_favorites(db)
