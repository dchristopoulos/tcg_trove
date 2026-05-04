from sqlalchemy.orm import Session

from app.db.models.search_log import SearchLog


def create_search_log(db: Session, *, user_id: int | None, query: str, filters: str) -> SearchLog:
    item = SearchLog(user_id=user_id, query=query, filters=filters)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_search_logs(db: Session) -> list[SearchLog]:
    return db.query(SearchLog).all()
