"""Cost-control gate for the token-spending endpoints.

Two server-enforced layers sit in front of POST /repos/index and POST /chat:

1. A shared access code (X-Access-Code header) compared to ``settings.access_code``.
2. A global daily quota in Redis, keyed by UTC date so it resets automatically.

Both are applied as FastAPI dependencies. The quota dependency declares the
access-code check as a sub-dependency, so FastAPI runs the access-code check
FIRST — an unauthorized request raises before any Redis INCR, never consuming
quota and never reaching the endpoint body (no OpenAI call).

The Redis connection reuses ``settings.redis_url`` — the same instance slowapi
and Celery already use. ``redis`` ships transitively via ``celery[redis]``.
"""

from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException

from app.config import get_settings

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return a process-wide async Redis client built from ``redis_url``.

    A plain callable (not cached via lru_cache) so tests can swap it through
    ``app.dependency_overrides[get_redis]``.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            get_settings().redis_url, decode_responses=True
        )
    return _redis_client


async def require_access_code(
    x_access_code: str | None = Header(default=None),
) -> None:
    """Reject requests without a valid X-Access-Code header.

    An unset ``access_code`` setting fails closed (rejects everything) so the
    gate is never accidentally open in production.
    """
    expected = get_settings().access_code
    if not expected or x_access_code != expected:
        raise HTTPException(
            status_code=401, detail="Invalid or missing access code"
        )


def daily_quota(counter: str, ceiling_field: str):
    """Build a dependency enforcing a global daily ceiling for ``counter``.

    ``ceiling_field`` names the ``Settings`` attribute holding the limit, read
    live at request time so it is tunable without a redeploy.

    Atomicity: we INCR first (atomic, race-safe) and inspect the returned value.
    If it exceeds the ceiling we DECR back, so a rejected request never
    permanently inflates the counter and concurrent requests can never let more
    than ``ceiling`` requests through.
    """

    async def _dependency(
        _: None = Depends(require_access_code),
        redis: aioredis.Redis = Depends(get_redis),
    ) -> None:
        settings = get_settings()
        ceiling = getattr(settings, ceiling_field)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"quota:{counter}:{day}"

        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, settings.quota_ttl_seconds)
        if count > ceiling:
            await redis.decr(key)
            raise HTTPException(
                status_code=429,
                detail="Demo is at capacity for today. Please try again tomorrow.",
            )

    return _dependency


require_index_quota = daily_quota("index", "quota_index_daily")
require_chat_quota = daily_quota("chat", "quota_chat_daily")
