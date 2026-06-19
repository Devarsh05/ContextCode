"""CORS configuration tests.

Verifies the allowed origins are assembled from CORS_ALLOW_ORIGINS and that
credentials are OFF (no auth → credentialed CORS would be a footgun). The
Access-Control-Allow-Origin header is still emitted for an allowed origin,
including on the GET /repos/{id}/status SSE endpoint (checked via a preflight,
which the middleware answers without starting the stream or touching the DB).
"""

import os
import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings

ALLOWED_ORIGIN = "http://localhost:3000"


def test_cors_origins_parsed_from_env():
    with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": "https://a.com, https://b.com ,"}):
        origins = get_settings().cors_origins
    assert origins == ["https://a.com", "https://b.com"]


def test_cors_default_origin_when_unset():
    env = {k: v for k, v in os.environ.items() if k != "CORS_ALLOW_ORIGINS"}
    with patch.dict(os.environ, env, clear=True):
        assert get_settings().cors_origins == ["http://localhost:3000"]


@pytest.mark.asyncio
async def test_cors_allows_origin_with_credentials_off():
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    # Credentials are disabled — Starlette omits the allow-credentials header.
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.asyncio
async def test_cors_preflight_covers_sse_status_endpoint():
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            f"/repos/{uuid.uuid4()}/status",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "access-control-allow-credentials" not in response.headers
