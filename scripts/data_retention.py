from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.db.models.audit_log import AuditLog
from app.db.models.inquiry_message import InquiryMessage
from app.db.models.search_log import SearchLog
from app.db.session import SessionLocal


def _prune_uploads() -> int:
    uploads_dir = Path(settings.media_dir)
    if not uploads_dir.exists():
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=max(int(settings.media_upload_retention_days), 1))
    removed = 0
    for item in uploads_dir.iterdir():
        if not item.is_file():
            continue
        modified = datetime.fromtimestamp(item.stat().st_mtime, tz=UTC)
        if modified < cutoff:
            item.unlink(missing_ok=True)
            removed += 1
    return removed


def main() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        inquiry_cutoff = now - timedelta(days=max(int(settings.inquiry_message_retention_days), 1))
        search_cutoff = now - timedelta(days=max(int(settings.search_log_retention_days), 1))
        audit_cutoff = now - timedelta(days=max(int(settings.audit_log_retention_days), 1))

        deleted_inquiry = (
            db.query(InquiryMessage).filter(InquiryMessage.created_at < inquiry_cutoff).delete(synchronize_session=False)
        )
        deleted_search = db.query(SearchLog).filter(SearchLog.created_at < search_cutoff).delete(synchronize_session=False)
        deleted_audit = db.query(AuditLog).filter(AuditLog.created_at < audit_cutoff).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    deleted_uploads = _prune_uploads()
    print(
        "Retention complete:",
        f"inquiry_messages={deleted_inquiry}",
        f"search_logs={deleted_search}",
        f"audit_logs={deleted_audit}",
        f"uploads={deleted_uploads}",
    )


if __name__ == "__main__":
    main()

