import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.middleware.request_context import get_request_context


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = get_request_context()
        record.request_id = context.get("request_id") or "-"
        record.ip_address = context.get("ip_address") or "-"
        record.user_agent = context.get("user_agent") or "-"
        return True


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    log_format = "%(asctime)s %(levelname)s [%(name)s] req_id=%(request_id)s ip=%(ip_address)s ua=\"%(user_agent)s\" %(message)s"
    formatter = logging.Formatter(log_format)
    context_filter = RequestContextFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)

    log_dir = Path(__file__).resolve().parents[2] / ".local" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "tcg_trove.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
