import asyncio
from collections import defaultdict

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.session import AsyncSessionLocal
from app.services.rate_limit_service import async_consume_rate_limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, api_limit_per_minute: int = 120, login_limit_per_minute: int = 20):
        super().__init__(app)
        self.api_limit_per_minute = api_limit_per_minute
        self.login_limit_per_minute = login_limit_per_minute
        self._scope_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _get_limit(self, path: str) -> int | None:
        if path in {"/login", "/api/v1/users/login-init", "/api/v1/users/login-verify"}:
            return self.login_limit_per_minute
        if path.startswith("/api/v1/"):
            return self.api_limit_per_minute
        return None

    async def dispatch(self, request, call_next):
        limit = self._get_limit(request.url.path)
        if limit is None:
            return await call_next(request)

        client_ip = request.client.host if request.client is not None else "unknown"
        key = f"{client_ip}:{request.url.path}"

        # Serialize checks per scope key in-process to avoid race bursts.
        async with self._scope_locks[key]:
            async with AsyncSessionLocal() as db:
                allowed = await async_consume_rate_limit(db, scope_key=key, limit=limit, window_seconds=60)

        if not allowed:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        return await call_next(request)
