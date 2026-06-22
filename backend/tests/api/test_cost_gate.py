"""Tests for the cost-control gate.

Two gates are exercised here:
- POST /repos/index — access code + global daily Redis quota (date-stamped key).
- POST /chat — public, demo-session gated, demo-repo-only, with a per-session
  cap plus the global daily cap (Phase C).

Redis is an in-memory ``fakeredis`` async client, swapped in via
``dependency_overrides`` — matching how conftest overrides ``get_db``.
``get_settings()`` reads os.environ live, so ACCESS_CODE / quota ceilings are set
per-test with ``patch.dict``.

This feature is Redis-only and adds no DB schema, so the known SQLite-vs-Postgres
test gap does not apply here.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fakeredis.aioredis import FakeRedis

from app.api.cost_gate import daily_quota
from app.models.repository import Repository
from app.rag.pipeline import Citation

_ACCESS_CODE = "test-code"
_SESSION_ID = "demo-session-abc"

_CITATION = Citation(
    file_path="pkg/mod.py",
    function_name="f",
    start_line=1,
    end_line=2,
    chunk_type="function",
    snippet="def f(): ...",
)
_MOCK_ANSWER = {"answer": "answer [1]", "citations": [_CITATION]}


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _global_key(counter: str, day: str | None = None) -> str:
    return f"quota:{counter}:global:{day or _utc_day()}"


def _session_key(session_id: str) -> str:
    return f"quota:chat:session:{session_id}"


@pytest_asyncio.fixture
async def fake_redis(async_client):
    """Run the REAL cost gate against an in-memory async Redis.

    Depends on ``async_client`` so it runs after that fixture's default
    gate-bypass overrides are installed, then pops them so these tests exercise
    the real access-code / demo-session / quota dependencies, with ``get_redis``
    pointed at ``fakeredis``.
    """
    from app.api.cost_gate import get_redis, require_chat_access, require_index_quota
    from app.main import app

    app.dependency_overrides.pop(require_index_quota, None)
    app.dependency_overrides.pop(require_chat_access, None)

    client = FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: client
    yield client
    app.dependency_overrides.pop(get_redis, None)
    await client.aclose()


async def _make_demo_repo(db_session, *, is_demo: bool = True) -> Repository:
    repo = Repository(
        url=f"https://github.com/demo/{os.urandom(4).hex()}",
        name="demo-repo",
        status="completed",
        is_demo=is_demo,
    )
    db_session.add(repo)
    await db_session.commit()
    return repo


# ── /repos/index access code ──────────────────────────────────────────────────

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
    assert await fake_redis.get(_global_key("index")) is None


async def test_index_wrong_access_code_returns_401(async_client, fake_redis):
    with patch.dict(os.environ, {"ACCESS_CODE": _ACCESS_CODE}):
        response = await async_client.post(
            "/repos/index",
            json={"repo_url": "https://github.com/octocat/Hello-World"},
            headers={"X-Access-Code": "wrong"},
        )

    assert response.status_code == 401
    assert await fake_redis.get(_global_key("index")) is None


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
    assert await fake_redis.get(_global_key("index")) == "1"


# ── /chat: public + demo session + demo-repo-only + quotas ────────────────────

async def test_chat_valid_session_demo_repo_no_access_code_succeeds(
    async_client, db_session, fake_redis
):
    repo = await _make_demo_repo(db_session)
    await fake_redis.set(f"demo:session:{_SESSION_ID}", "1.2.3.4", ex=3600)

    with patch("app.rag.pipeline.RAGPipeline.answer", new_callable=AsyncMock) as mock_answer:
        mock_answer.return_value = _MOCK_ANSWER

        # No X-Access-Code header — chat is public now.
        response = await async_client.post(
            "/chat",
            json={"repo_id": str(repo.id), "question": "How does it work?"},
            headers={"X-Demo-Session": _SESSION_ID},
        )

    assert response.status_code == 200
    assert await fake_redis.get(_session_key(_SESSION_ID)) == "1"
    assert await fake_redis.get(_global_key("chat")) == "1"


async def test_chat_per_session_cap_returns_429_and_global_not_incremented(
    async_client, db_session, fake_redis
):
    repo = await _make_demo_repo(db_session)
    await fake_redis.set(f"demo:session:{_SESSION_ID}", "1.2.3.4", ex=3600)
    # Pre-fill the per-session counter to the default per-session cap (20).
    await fake_redis.set(_session_key(_SESSION_ID), 20)

    with patch("app.rag.pipeline.RAGPipeline.answer", new_callable=AsyncMock) as mock_answer:
        response = await async_client.post(
            "/chat",
            json={"repo_id": str(repo.id), "question": "anything"},
            headers={"X-Demo-Session": _SESSION_ID},
        )

    assert response.status_code == 429
    # The per-session INCR was rolled back, and we never reached the global counter.
    assert await fake_redis.get(_session_key(_SESSION_ID)) == "20"
    assert await fake_redis.get(_global_key("chat")) is None
    mock_answer.assert_not_called()


async def test_chat_global_cap_returns_429_and_rolls_back_per_session(
    async_client, db_session, fake_redis
):
    repo = await _make_demo_repo(db_session)
    await fake_redis.set(f"demo:session:{_SESSION_ID}", "1.2.3.4", ex=3600)
    # Per-session counter has headroom; the global counter is at the daily cap (100).
    await fake_redis.set(_session_key(_SESSION_ID), 5)
    await fake_redis.set(_global_key("chat"), 100)

    with patch("app.rag.pipeline.RAGPipeline.answer", new_callable=AsyncMock) as mock_answer:
        response = await async_client.post(
            "/chat",
            json={"repo_id": str(repo.id), "question": "anything"},
            headers={"X-Demo-Session": _SESSION_ID},
        )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Demo is at capacity for today. Please try again tomorrow."
    )
    # Global DECR cancels its INCR, and the per-session counter is rolled back to 5.
    assert await fake_redis.get(_global_key("chat")) == "100"
    assert await fake_redis.get(_session_key(_SESSION_ID)) == "5"
    mock_answer.assert_not_called()


async def test_chat_non_demo_repo_returns_403(
    async_client, db_session, fake_redis
):
    repo = await _make_demo_repo(db_session, is_demo=False)
    await fake_redis.set(f"demo:session:{_SESSION_ID}", "1.2.3.4", ex=3600)

    response = await async_client.post(
        "/chat",
        json={"repo_id": str(repo.id), "question": "anything"},
        headers={"X-Demo-Session": _SESSION_ID},
    )

    assert response.status_code == 403
    # No quota consumed on a demo-repo rejection.
    assert await fake_redis.get(_session_key(_SESSION_ID)) is None
    assert await fake_redis.get(_global_key("chat")) is None


async def test_chat_missing_session_returns_401(
    async_client, db_session, fake_redis
):
    repo = await _make_demo_repo(db_session)

    # No X-Demo-Session header at all.
    response = await async_client.post(
        "/chat",
        json={"repo_id": str(repo.id), "question": "anything"},
    )

    assert response.status_code == 401
    assert await fake_redis.get(_global_key("chat")) is None


async def test_chat_unknown_session_returns_401(
    async_client, db_session, fake_redis
):
    repo = await _make_demo_repo(db_session)

    # Header present but the session id is not in Redis (expired / never minted).
    response = await async_client.post(
        "/chat",
        json={"repo_id": str(repo.id), "question": "anything"},
        headers={"X-Demo-Session": "does-not-exist"},
    )

    assert response.status_code == 401
    assert await fake_redis.get(_global_key("chat")) is None


async def test_chat_counter_under_yesterday_does_not_count_today(
    async_client, db_session, fake_redis
):
    repo = await _make_demo_repo(db_session)
    await fake_redis.set(f"demo:session:{_SESSION_ID}", "1.2.3.4", ex=3600)

    # Yesterday's global counter is maxed out — it must not gate today.
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    await fake_redis.set(_global_key("chat", yesterday), 100)

    with patch("app.rag.pipeline.RAGPipeline.answer", new_callable=AsyncMock) as mock_answer:
        mock_answer.return_value = _MOCK_ANSWER

        response = await async_client.post(
            "/chat",
            json={"repo_id": str(repo.id), "question": "anything"},
            headers={"X-Demo-Session": _SESSION_ID},
        )

    assert response.status_code == 200
    # Today's counter starts fresh at 1; yesterday's is untouched.
    assert await fake_redis.get(_global_key("chat")) == "1"
    assert await fake_redis.get(_global_key("chat", yesterday)) == "100"


# ── Atomicity: concurrent requests near the ceiling don't overshoot ───────────

async def test_concurrent_requests_do_not_overshoot_ceiling(fake_redis):
    """Fire many concurrent quota checks against the index gate's ceiling of 2.

    Exercised at the dependency level on the date-stamped global counter. The
    chat gate no longer uses ``daily_quota`` (it has its own per-session + global
    logic), but the factory still backs /repos/index, and INCR-then-check is
    atomic — so exactly ``ceiling`` calls pass and the counter never climbs past
    it. A GET-then-SET impl would overshoot under interleaving.
    """
    dep = daily_quota("index", "quota_index_daily")

    async def attempt() -> int:
        try:
            # _ is the access-code sub-dependency result (already passed).
            await dep(_=None, redis=fake_redis)
            return 200
        except HTTPException as exc:
            return exc.status_code

    with patch.dict(os.environ, {"ACCESS_CODE": _ACCESS_CODE, "QUOTA_INDEX_DAILY": "2"}):
        results = await asyncio.gather(*(attempt() for _ in range(10)))

    assert results.count(200) == 2
    assert results.count(429) == 8
    assert await fake_redis.get(_global_key("index")) == "2"
