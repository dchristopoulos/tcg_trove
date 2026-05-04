from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.favorite import Favorite


def get_user_favorites(db: Session, user_id: int) -> list[Favorite]:
    return db.query(Favorite).filter(Favorite.user_id == user_id).all()


def get_all_favorites(db: Session) -> list[Favorite]:
    return db.query(Favorite).all()


def get_favorite(db: Session, user_id: int, listing_id: int) -> Favorite | None:
    return db.query(Favorite).filter(Favorite.user_id == user_id, Favorite.listing_id == listing_id).first()


def create_favorite(db: Session, user_id: int, listing_id: int) -> Favorite:
    favorite = Favorite(user_id=user_id, listing_id=listing_id)
    db.add(favorite)
    try:
        db.commit()
        db.refresh(favorite)
        return favorite
    except IntegrityError:
        db.rollback()
        existing = get_favorite(db, user_id, listing_id)
        if existing is not None:
            return existing
        raise


def delete_favorite(db: Session, favorite: Favorite) -> None:
    db.delete(favorite)
    db.commit()
