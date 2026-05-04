from sqlalchemy.orm import Session

from app.db.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: str,
    details: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    item = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
