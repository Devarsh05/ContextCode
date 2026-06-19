"""Rate limiting returns 429 past the threshold.

Builds a throwaway app with the real limiter factory + handler (memory storage,
a low limit) so the behavior is exercised deterministically without Redis. The
production endpoints use the same `limiter`/handler wiring (see app/main.py,
app/api/repos.py, app/api/chat.py).
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.rate_limit import RateLimitExceeded, build_limiter, rate_limit_handler


def _make_app(limit: str) -> FastAPI:
    limiter = build_limiter("memory://")
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    @app.get("/ping")
    @limiter.limit(limit)
    async def ping(request: Request):
        return {"ok": True}

    return app


def test_returns_429_past_threshold():
    client = TestClient(_make_app("2/minute"))

    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    # Third request within the window is rejected.
    assert client.get("/ping").status_code == 429


def test_under_threshold_all_succeed():
    client = TestClient(_make_app("5/minute"))

    for _ in range(5):
        assert client.get("/ping").status_code == 200
