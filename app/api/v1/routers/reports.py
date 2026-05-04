from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.report import MonthlySupervisorReportRead
from app.services.favorite_service import all_favorites_use_case
from app.services.inquiry_service import all_inquiries_use_case
from app.services.search_service import list_search_logs_use_case

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly", response_model=MonthlySupervisorReportRead)
def monthly_supervisor_report(
    db: Session = Depends(get_db),
    _supervisor: User = Depends(require_permission("view_reports")),
):
    inquiries = all_inquiries_use_case(db)
    search_logs = list_search_logs_use_case(db)
    favorites = all_favorites_use_case(db)
    trend_counter = Counter(item.query for item in search_logs if item.query)
    top_searches = [{"query": query, "count": count} for query, count in trend_counter.most_common(10)]
    return {
        "inquiries_count": len(inquiries),
        "saved_properties_count": len(favorites),
        "top_searches": top_searches,
    }
