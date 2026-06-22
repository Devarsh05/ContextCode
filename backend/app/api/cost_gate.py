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
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChatRequest
from app.config import get_settings
from app.models.database import get_db
from app.models.repository import Repository


def _utc_day() -> str:
    """Current UTC date as ``YYYY-MM-DD`` — the date stamp on daily quota keys."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

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
        key = f"quota:{counter}:global:{_utc_day()}"

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


async def require_chat_access(
    body: ChatRequest,
    x_demo_session: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    """Public chat gate: demo session + demo-repo-only + per-session/global quota.

    Replaces the access-code gate on /chat (indexing keeps the access code). The
    steps run in a fixed order and never consume quota on a later failure:

      a. Validate the X-Demo-Session header against ``demo:session:{id}`` in Redis
         (minted by POST /demo/session). Missing/expired → 401.
      b. The target repo must exist and be a demo repo. Missing → 404; non-demo →
         403 (public chat is demo repos only).
      c. INCR the per-session counter; over the per-session cap → DECR, 429. Its
         TTL tracks the session's remaining lifetime.
      d. INCR the dated global counter; over the daily cap → DECR global AND DECR
         the per-session counter from (c), 429.

    INCR-then-check is atomic, so concurrent requests can never overshoot a cap.
    """
    settings = get_settings()

    # (a) Demo session — Redis TTL makes expiry automatic (expired key reads None).
    session_key = f"demo:session:{x_demo_session}"
    if not x_demo_session or await redis.get(session_key) is None:
        raise HTTPException(status_code=401, detail="Missing or invalid demo session")

    # (b) Demo-repo-only.
    try:
        repo_uuid = UUID(body.repo_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Repository not found")

    result = await db.execute(select(Repository).where(Repository.id == repo_uuid))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not repo.is_demo:
        raise HTTPException(
            status_code=403, detail="Chat is available for demo repositories only"
        )

    # (c) Per-session cap. TTL tracks the session so the counter dies with it.
    session_counter = f"quota:chat:session:{x_demo_session}"
    session_count = await redis.incr(session_counter)
    if session_count == 1:
        session_ttl = await redis.ttl(session_key)
        if session_ttl and session_ttl > 0:
            await redis.expire(session_counter, session_ttl)
    if session_count > settings.quota_chat_per_session:
        await redis.decr(session_counter)
        raise HTTPException(
            status_code=429,
            detail="You've reached the demo message limit for this session.",
        )

    # (d) Global daily cap. Roll back (c) too if we trip the ceiling here.
    global_counter = f"quota:chat:global:{_utc_day()}"
    global_count = await redis.incr(global_counter)
    if global_count == 1:
        await redis.expire(global_counter, settings.quota_ttl_seconds)
    if global_count > settings.quota_chat_daily:
        await redis.decr(global_counter)
        await redis.decr(session_counter)
        raise HTTPException(
            status_code=429,
            detail="Demo is at capacity for today. Please try again tomorrow.",
        )
