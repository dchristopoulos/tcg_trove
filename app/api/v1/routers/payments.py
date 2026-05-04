from typing import Any, cast

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_permission
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.payment import PaymentCreate, PaymentRead
from app.services.payment_service import create_payment_use_case, get_recent_payment_logs_use_case

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentRead)
def create_payment_endpoint(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return create_payment_use_case(
        db,
        payload,
        actor_user_id=int(cast(Any, _current_user.id)),
        actor_role=str(cast(Any, _current_user.role)),
    )


@router.get("/logs", response_model=list[PaymentRead])
def payment_logs_endpoint(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("view_reports")),
):
    return get_recent_payment_logs_use_case(db)
