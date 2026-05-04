import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import record_request

logger = logging.getLogger("tcg_trove.request")
_request_context: ContextVar[dict[str, str | None] | None] = ContextVar("request_context", default=None)


def get_request_context() -> dict[str, str | None]:
    return _request_context.get() or {}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        token = _request_context.set(
            {
                "request_id": request_id,
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s -> %s %.2fms req_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                request_id,
            )
            record_request(method=request.method, path=request.url.path, status_code=response.status_code)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _request_context.reset(token)
