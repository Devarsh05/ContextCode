"""CORS configuration tests.

Verifies CORSMiddleware emits the Access-Control-Allow-Origin header for an
allowed origin, including on the GET /repos/{id}/status SSE endpoint (checked
via a preflight request, which the middleware answers without starting the
stream or touching the DB).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

ALLOWED_ORIGIN = "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_headers_present_for_allowed_origin():
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


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
    assert response.headers["access-control-allow-credentials"] == "true"
