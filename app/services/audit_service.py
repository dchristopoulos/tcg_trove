from sqlalchemy.orm import Session

from app.managers.audit_manager import create_audit_log
from app.middleware.request_context import get_request_context


def record_audit_event(
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
) -> None:
    context = get_request_context()
    resolved_ip = ip_address if ip_address is not None else context.get("ip_address")
    resolved_user_agent = user_agent if user_agent is not None else context.get("user_agent")
    resolved_request_id = request_id if request_id is not None else context.get("request_id")

    create_audit_log(
        db,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=resolved_ip,
        user_agent=resolved_user_agent,
        request_id=resolved_request_id,
    )
