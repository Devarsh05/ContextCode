"""Tests for POST /demo/session (Cloudflare Turnstile verification + minting).

The outbound Turnstile call is mocked with ``httpx.MockTransport`` swapped in via
``app.dependency_overrides[get_http_client]`` — no real HTTP leaves the process.
Redis is an in-memory ``fakeredis`` async client, also injected through
``dependency_overrides`` (matching the cost-gate tests). ``get_settings()`` reads
os.environ live, so ``TURNSTILE_SECRET_KEY`` is set per-test with ``patch.dict``.
"""

import os
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis

_SECRET = "test-secret"


@pytest_asyncio.fixture
async def fake_redis(async_client):
    """Point the demo-session route at an in-memory async Redis."""
    from app.api.cost_gate import get_redis
    from app.main import app

    client = FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: client
    yield client
    app.dependency_overrides.pop(get_redis, None)
    await client.aclose()


@pytest_asyncio.fixture
async def turnstile():
    """Install a mock Turnstile endpoint and expose request capture + control.

    Yields an object whose ``success`` flag controls the verdict, ``calls``
    records every outbound request, and ``last_form`` parses the most recent
    form body so tests can assert the ``remoteip`` that was sent.
    """
    from app.api.demo_session import get_http_client
    from app.main import app

    class _Mock:
        def __init__(self) -> None:
            self.success = True
            self.calls: list[httpx.Request] = []

        @property
        def last_form(self) -> dict[str, str]:
            body = self.calls[-1].content.decode()
            return dict(httpx.QueryParams(body))

    mock = _Mock()

    def handler(request: httpx.Request) -> httpx.Response:
        mock.calls.append(request)
        return httpx.Response(200, json={"success": mock.success})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_http_client] = lambda: client
    yield mock
    app.dependency_overrides.pop(get_http_client, None)
    await client.aclose()


async def _keys(redis: FakeRedis) -> list[str]:
    return await redis.keys("demo:session:*")


async def test_success_returns_200_and_stores_session_with_ttl(
    async_client, fake_redis, turnstile
):
    turnstile.success = True
    with patch.dict(os.environ, {"TURNSTILE_SECRET_KEY": _SECRET}):
        response = await async_client.post(
            "/demo/session", json={"token": "good-token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["expires_in"] == 3600
    session_id = body["session_id"]
    assert session_id

    key = f"demo:session:{session_id}"
    assert await fake_redis.exists(key) == 1
    ttl = await fake_redis.ttl(key)
    assert 0 < ttl <= 3600


async def test_turnstile_failure_returns_403_and_stores_nothing(
    async_client, fake_redis, turnstile
):
    turnstile.success = False
    with patch.dict(os.environ, {"TURNSTILE_SECRET_KEY": _SECRET}):
        response = await async_client.post(
            "/demo/session", json={"token": "bad-token"}
        )

    assert response.status_code == 403
    assert await _keys(fake_redis) == []


async def test_missing_secret_fails_closed_without_calling_cloudflare(
    async_client, fake_redis, turnstile
):
    # No TURNSTILE_SECRET_KEY in the environment.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TURNSTILE_SECRET_KEY", None)
        response = await async_client.post(
            "/demo/session", json={"token": "whatever"}
        )

    assert response.status_code == 403
    assert turnstile.calls == []  # never reached out to Cloudflare
    assert await _keys(fake_redis) == []


async def test_stored_value_carries_resolved_client_ip(
    async_client, fake_redis, turnstile
):
    turnstile.success = True
    with patch.dict(os.environ, {"TURNSTILE_SECRET_KEY": _SECRET}):
        response = await async_client.post(
            "/demo/session",
            json={"token": "good-token"},
            headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
        )

    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # First hop of X-Forwarded-For is both stored and sent to Cloudflare.
    assert await fake_redis.get(f"demo:session:{session_id}") == "1.2.3.4"
    assert turnstile.last_form["remoteip"] == "1.2.3.4"
