"""Tests for the cost-control gate (access code + global daily Redis quota).

The gate guards POST /repos/index and POST /chat only. Redis is provided by an
in-memory ``fakeredis`` async client, swapped in via ``dependency_overrides`` —
matching how conftest overrides ``get_db``. ``get_settings()`` reads os.environ
live, so ACCESS_CODE / quota ceilings are set per-test with ``patch.dict``.

This feature is Redis-only and adds no DB schema, so the known SQLite-vs-Postgres
test gap does not apply here.
"""

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fakeredis.aioredis import FakeRedis

from app.api.cost_gate import daily_quota
from app.models.repository import Repository
from app.rag.pipeline import Citation

_ACCESS_CODE = "test-code"

_CITATION = Citation(
    file_path="pkg/mod.py",
    function_name="f",
    start_line=1,
    end_line=2,
    chunk_type="function",
    snippet="def f(): ...",
)
_MOCK_ANSWER = {"answer": "answer [1]", "citations": [_CITATION]}


def _quota_key(counter: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"quota:{counter}:{day}"


@pytest_asyncio.fixture
async def fake_redis(async_client):
    """Run the REAL cost gate against an in-memory async Redis.

    Depends on ``async_client`` so it runs after that fixture's default
    gate-bypass overrides are installed, then pops them so these tests exercise
    the real access-code + quota dependencies, with ``get_redis`` pointed at
    ``fakeredis``.
    """
    from app.api.cost_gate import get_redis, require_chat_quota, require_index_quota
    from app.main import app

    app.dependency_overrides.pop(require_index_quota, None)
    app.dependency_overrides.pop(require_chat_quota, None)

    client = FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: client
    yield client
    app.dependency_overrides.pop(get_redis, None)
    await client.aclose()


# ── Access code ───────────────────────────────────────────────────────────────

async def test_index_missing_access_code_returns_401_and_consumes_no_quota(
    async_client, fake_redis
):
    with patch.dict(os.environ, {"ACCESS_CODE": _ACCESS_CODE}):
        response = await async_client.post(
            "/repos/index",
            json={"repo_url": "https://github.com/octocat/Hello-World"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing access code"
    # The increment must happen only after the access-code check passes.
    assert await fake_redis.get(_quota_key("index")) is None


async def test_index_wrong_access_code_returns_401(async_client, fake_redis):
    with patch.dict(os.environ, {"ACCESS_CODE": _ACCESS_CODE}):
        response = await async_client.post(
            "/repos/index",
            json={"repo_url": "https://github.com/octocat/Hello-World"},
            headers={"X-Access-Code": "wrong"},
        )

    assert response.status_code == 401
    assert await fake_redis.get(_quota_key("index")) is None


# ── Under quota → proceeds + increments ──────────────────────────────────────

async def test_index_valid_code_under_quota_proceeds_and_increments(
    async_client, fake_redis
):
    with patch.dict(os.environ, {"ACCESS_CODE": _ACCESS_CODE}), \
         patch("app.api.repos.index_repository") as mock_task:
        mock_task.delay.return_value = None

        response = await async_client.post(
            "/repos/index",
            json={"repo_url": "https://github.com/octocat/Hello-World"},
            headers={"X-Access-Code": _ACCESS_CODE},
        )

    assert response.status_code == 200
    mock_task.delay.assert_called_once()
    assert await fake_redis.get(_quota_key("index")) == "1"


async def test_chat_valid_code_under_quota_proceeds_and_increments(
    async_client, db_session, fake_redis
):
    repo = Repository(
        url="https://github.com/encode/databases",
        name="databases",
        status="completed",
    )
    db_session.add(repo)
    await db_session.commit()

    with patch.dict(os.environ, {"ACCESS_CODE": _ACCESS_CODE}), \
         patch("app.rag.pipeline.RAGPipeline.answer", new_callable=AsyncMock) as mock_answer:
        mock_answer.return_value = _MOCK_ANSWER

        response = await async_client.post(
            "/chat",
            json={"repo_id": str(repo.id), "question": "How does it work?"},
            headers={"X-Access-Code": _ACCESS_CODE},
        )

    assert response.status_code == 200
    assert await fake_redis.get(_quota_key("chat")) == "1"


# ── At ceiling → 429, no further increment, no OpenAI call ────────────────────

async def test_chat_at_ceiling_returns_429_and_does_not_increment(
    async_client, db_session, fake_redis
):
    repo = Repository(
        url="https://github.com/encode/starlette",
        name="starlette",
        status="completed",
    )
    db_session.add(repo)
    await db_session.commit()

    # Pre-fill the counter to the default chat ceiling (50).
    await fake_redis.set(_quota_key("chat"), 50)

    with patch.dict(os.environ, {"ACCESS_CODE": _ACCESS_CODE}), \
         patch("app.rag.pipeline.RAGPipeline.answer", new_callable=AsyncMock) as mock_answer:
        response = await async_client.post(
            "/chat",
            json={"repo_id": str(repo.id), "question": "anything"},
            headers={"X-Access-Code": _ACCESS_CODE},
        )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Demo is at capacity for today. Please try again tomorrow."
    )
    # DECR cancels the INCR — the counter is unchanged and the LLM was not called.
    assert await fake_redis.get(_quota_key("chat")) == "50"
    mock_answer.assert_not_called()


# ── Atomicity: concurrent requests near the ceiling don't overshoot ───────────

async def test_concurrent_requests_do_not_overshoot_ceiling(fake_redis):
    """Fire many concurrent quota checks against a ceiling of 2.

    Exercised at the dependency level (the shared test ``db_session`` is not
    concurrency-safe). INCR-then-check is atomic, so exactly ``ceiling`` calls
    pass and the counter never climbs past it — a GET-then-SET impl would
    overshoot under interleaving.
    """
    dep = daily_quota("chat", "quota_chat_daily")

    async def attempt() -> int:
        try:
            # _ is the access-code sub-dependency result (already passed).
            await dep(_=None, redis=fake_redis)
            return 200
        except HTTPException as exc:
            return exc.status_code

    with patch.dict(os.environ, {"ACCESS_CODE": _ACCESS_CODE, "QUOTA_CHAT_DAILY": "2"}):
        results = await asyncio.gather(*(attempt() for _ in range(10)))

    assert results.count(200) == 2
    assert results.count(429) == 8
    assert await fake_redis.get(_quota_key("chat")) == "2"
