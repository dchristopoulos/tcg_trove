import logging
import uuid
from typing import Any, cast

from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidPaymentMethodError,
    PermissionDeniedError,
    ReservationNotFoundError,
)
from app.db.models.payment_log import PaymentLog
from app.managers.payment_manager import create_payment_log, list_recent_payment_logs
from app.managers.reservation_manager import get_reservation_by_id
from app.schemas.payment import PaymentCreate
from app.services.audit_service import record_audit_event

ALLOWED_PAYMENT_METHODS = {"credit_card", "bank_transfer", "paypal"}
logger = logging.getLogger("tcg_trove.payments")


def create_payment_use_case(db: Session, payload: PaymentCreate, *, actor_user_id: int, actor_role: str) -> PaymentLog:
    if payload.payment_method not in ALLOWED_PAYMENT_METHODS:
        raise InvalidPaymentMethodError
    reservation = get_reservation_by_id(db, payload.reservation_id)
    if reservation is None:
        raise ReservationNotFoundError
    if actor_role != "admin" and actor_user_id != int(cast(Any, reservation.user_id)):
        raise PermissionDeniedError
    payment = create_payment_log(
        db,
        reservation_id=payload.reservation_id,
        payment_method=payload.payment_method,
        amount=payload.amount,
        currency=payload.currency,
        transaction_ref=uuid.uuid4().hex,
    )
    try:
        record_audit_event(
            db,
            actor_user_id=actor_user_id,
            action="payment_logged",
            target_type="payment",
            target_id=str(payment.id),
            details=f"reservation_id={payload.reservation_id} amount={payload.amount}",
        )
    except Exception:
        logger.exception("Failed to record payment audit event", extra={"payment_id": payment.id})
    return payment


def get_recent_payment_logs_use_case(db: Session) -> list[PaymentLog]:
    return list_recent_payment_logs(db)
