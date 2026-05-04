from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models.payment_log import PaymentLog


def create_payment_log(
    db: Session,
    *,
    reservation_id: int,
    payment_method: str,
    amount: int,
    currency: str,
    transaction_ref: str,
    status: str = "completed",
) -> PaymentLog:
    item = PaymentLog(
        reservation_id=reservation_id,
        payment_method=payment_method,
        amount=amount,
        currency=currency,
        transaction_ref=transaction_ref,
        status=status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_recent_payment_logs(db: Session) -> list[PaymentLog]:
    cutoff = datetime.now(UTC) - timedelta(days=90)
    return db.query(PaymentLog).filter(PaymentLog.created_at >= cutoff).all()
