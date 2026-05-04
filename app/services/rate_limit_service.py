import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.rate_limit_event import RateLimitEvent

logger = logging.getLogger("tcg_trove.rate_limit")
_redis_client: Any | None = None
_redis_disabled = False
_REDIS_WINDOW_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
if current <= tonumber(ARGV[2]) then
  return 1
end
return 0
"""


async def _get_redis_client() -> Any | None:
    global _redis_client, _redis_disabled
    redis_url = settings.rate_limit_redis_url.strip()
    if not redis_url or _redis_disabled:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as redis  # type: ignore[import-not-found]
    except Exception:
        logger.warning("Redis URL configured for rate limiting but redis package is unavailable")
        _redis_disabled = True
        return None
    _redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    return _redis_client


def consume_rate_limit(
    db: Session,
    *,
    scope_key: str,
    limit: int,
    window_seconds: int = 60,
) -> bool:
    now = datetime.now(UTC).replace(tzinfo=None)
    window_start = now - timedelta(seconds=window_seconds)
    retention_start = now - timedelta(seconds=max(int(settings.rate_limit_event_retention_seconds), window_seconds))

    try:
        # Cap table growth from one-off scope keys by pruning old records globally.
        db.query(RateLimitEvent).filter(
            RateLimitEvent.created_at < retention_start,
        ).delete(synchronize_session=False)

        db.query(RateLimitEvent).filter(
            RateLimitEvent.scope_key == scope_key,
            RateLimitEvent.created_at < window_start,
        ).delete(synchronize_session=False)

        current = (
            db.query(RateLimitEvent)
            .filter(
                RateLimitEvent.scope_key == scope_key,
                RateLimitEvent.created_at >= window_start,
            )
            .count()
        )
    except OperationalError:
        # Fail open if the table is temporarily unavailable; middleware should not crash requests.
        db.rollback()
        return True
    except Exception:
        db.rollback()
        logger.exception("Unexpected sync rate-limit failure")
        return False

    if current >= limit:
        db.commit()
        return False

    db.add(RateLimitEvent(scope_key=scope_key, created_at=now))
    db.commit()
    return True


async def async_consume_rate_limit(
    db: AsyncSession,
    *,
    scope_key: str,
    limit: int,
    window_seconds: int = 60,
) -> bool:
    redis_client = await _get_redis_client()
    if redis_client is not None:
        try:
            redis_key = f"ratelimit:{scope_key}"
            result = await redis_client.eval(
                _REDIS_WINDOW_LUA,
                1,
                redis_key,
                str(window_seconds),
                str(limit),
            )
            return bool(result == 1)
        except Exception:
            logger.exception("Redis rate limiting failed; falling back to database strategy")

    now = datetime.now(UTC).replace(tzinfo=None)
    window_start = now - timedelta(seconds=window_seconds)
    retention_start = now - timedelta(seconds=max(int(settings.rate_limit_event_retention_seconds), window_seconds))

    try:
        # Cap table growth from one-off scope keys by pruning old records globally.
        await db.execute(
            delete(RateLimitEvent).where(RateLimitEvent.created_at < retention_start)
        )

        await db.execute(
            delete(RateLimitEvent).where(
                RateLimitEvent.scope_key == scope_key,
                RateLimitEvent.created_at < window_start,
            )
        )

        result = await db.execute(
            select(func.count()).select_from(RateLimitEvent).where(
                RateLimitEvent.scope_key == scope_key,
                RateLimitEvent.created_at >= window_start,
            )
        )
        current = result.scalar() or 0
    except OperationalError:
        # Fail open if the table is temporarily unavailable; middleware should not crash requests.
        await db.rollback()
        return True
    except Exception:
        await db.rollback()
        logger.exception("Unexpected async rate-limit failure")
        return False

    if current >= limit:
        await db.commit()
        return False

    db.add(RateLimitEvent(scope_key=scope_key, created_at=now))
    await db.commit()
    return True
