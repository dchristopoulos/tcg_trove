from sqlalchemy.orm import Session

from app.db.models.search_log import SearchLog
from app.managers.search_manager import create_search_log, list_search_logs


def create_search_log_use_case(db: Session, *, user_id: int | None, query: str, filters: str) -> SearchLog:
    return create_search_log(db, user_id=user_id, query=query, filters=filters)


def list_search_logs_use_case(db: Session) -> list[SearchLog]:
    return list_search_logs(db)
