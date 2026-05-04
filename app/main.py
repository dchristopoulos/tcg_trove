import asyncio
import logging
import secrets
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.handlers import register_exception_handlers
from app.api.v1.routers import (
    favorites,
    gdpr,
    inquiries,
    listings,
    payments,
    reports,
    reservations,
    search,
    users,
    viewings,
)
from app.core.config import settings
from app.core.logger import configure_logging
from app.core.metrics import render_prometheus_metrics
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.middleware.body_size import BodySizeLimitMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.static_cache import StaticCacheMiddleware
from app.services.email_service import async_process_outbox
from app.web.deps import template_response
from app.web.routers import (
    account as web_account,
)
from app.web.routers import (
    admin as web_admin,
)
from app.web.routers import (
    auth as web_auth,
)
from app.web.routers import (
    base as web_base,
)
from app.web.routers import (
    dashboard as web_dashboard,
)
from app.web.routers import (
    listings as web_listings,
)
from app.web.routers import (
    messages as web_messages,
)
from app.web.routers import marketplace as web_marketplace

STATIC_DIR = Path(__file__).resolve().parent / "static"
logger = logging.getLogger("tcg_trove.startup")


def _initialize_sentry() -> None:
    if not settings.sentry_dsn.strip():
        return
    try:
        import sentry_sdk
    except Exception:
        logger.warning("Sentry DSN is set but sentry-sdk is not installed; skipping Sentry initialization")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.app_version,
        traces_sample_rate=float(settings.sentry_traces_sample_rate),
    )
    logger.info("Sentry initialized", extra={"environment": settings.app_env, "release": settings.app_version})


async def _email_outbox_worker() -> None:
    while True:
        try:
            await async_process_outbox(batch_size=settings.email_outbox_batch_size)
        except Exception:
            logger.exception("Email outbox worker cycle failed")
        await asyncio.sleep(max(int(settings.email_outbox_poll_seconds), 5))


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    _initialize_sentry()
    init_db()
    worker_task = None
    if settings.email_outbox_worker_enabled:
        worker_task = asyncio.create_task(_email_outbox_worker())
        logger.info("Email outbox worker started")
    yield
    if worker_task is not None:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)
app.state.app_env = settings.app_env
app.state.use_minified_assets = (STATIC_DIR / "styles.min.css").exists()
app.state.ux_events = deque(maxlen=2000)
register_exception_handlers(app)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(StaticCacheMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    RateLimitMiddleware,
    api_limit_per_minute=settings.api_rate_limit_per_minute,
    login_limit_per_minute=settings.login_rate_limit_per_minute,
)
app.add_middleware(BodySizeLimitMiddleware, max_body_size_bytes=settings.max_body_size_bytes)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.is_production,
)
_cors_origins = settings.allowed_origins_list
# Always include the React dev server origins in non-production environments
if not settings.is_production:
    _react_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if _cors_origins == ["*"]:
        _cors_origins = _react_origins
    else:
        for _o in _react_origins:
            if _o not in _cors_origins:
                _cors_origins.append(_o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "x-user-id", "x-session-token"],
    expose_headers=["x-user-id", "x-session-token"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str | bool]:
    db_ok = True
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    finally:
        db.close()
    return {
        "status": "ok" if db_ok else "degraded",
        "env": settings.app_env,
        "version": settings.app_version,
        "database_ok": db_ok,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/health/ready")
def health_ready() -> dict[str, str | bool]:
    db_ok = True
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    finally:
        db.close()
    payload = {
        "status": "ready" if db_ok else "not_ready",
        "database_ok": db_ok,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=payload)


@app.get("/metrics", response_class=PlainTextResponse)
def metrics(x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token")) -> str:
    configured_token = settings.metrics_auth_token.strip()
    if configured_token:
        if x_metrics_token is None or not secrets.compare_digest(configured_token, x_metrics_token):
            raise HTTPException(status_code=403, detail="Permission denied")
    return render_prometheus_metrics()

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/v1"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return template_response(request, "404.html", {}, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
            "method": request.method,
        },
    )
    if request.url.path.startswith("/api/v1"):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    return template_response(request, "500.html", {}, status_code=500)


app.include_router(users.router, prefix="/api/v1")
app.include_router(listings.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(favorites.router, prefix="/api/v1")
app.include_router(inquiries.router, prefix="/api/v1")
app.include_router(viewings.router, prefix="/api/v1")
app.include_router(reservations.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(gdpr.router, prefix="/api/v1")
app.include_router(web_base.router)
app.include_router(web_auth.router)
app.include_router(web_account.router)
app.include_router(web_dashboard.router)
app.include_router(web_admin.router)
app.include_router(web_listings.router)
app.include_router(web_messages.router)
app.include_router(web_marketplace.router)
