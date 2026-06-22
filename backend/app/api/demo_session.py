"""Demo-session minting gated by a Cloudflare Turnstile challenge.

POST /demo/session verifies a Turnstile response token server-side and, on
success, mints a short-lived opaque session id stored in Redis. A later phase
(not here) reads that session to admit demo traffic on the chat endpoint.

Fail-closed posture mirrors the access-code gate: an unset
``turnstile_secret_key`` rejects every request (it can't be verified), and a
``success=false`` verdict from Cloudflare is a 403.

The outbound verification call uses a process-wide ``httpx.AsyncClient`` exposed
through ``get_http_client`` — a plain callable (like ``cost_gate.get_redis``) so
tests can swap it via ``app.dependency_overrides`` with a MockTransport client.
"""

import secrets

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.cost_gate import get_redis
from app.api.schemas import DemoSessionRequest, DemoSessionResponse, ErrorResponse
from app.config import get_settings

router = APIRouter(prefix="/demo", tags=["demo"])

TURNSTILE_VERIFY_URL = (
    "https://challenges.cloudflare.com/turnstile/v0/siteverify"
)

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return a process-wide async HTTP client for outbound verification calls.

    A plain callable (not cached via lru_cache) so tests can swap it through
    ``app.dependency_overrides[get_http_client]``.
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


def _resolve_client_ip(request: Request) -> str | None:
    """Resolve the originating client IP once.

    Railway sits behind a proxy, so the real client is the first hop in
    ``X-Forwarded-For``. Fall back to the socket peer when the header is absent.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else None


@router.post(
    "/session",
    response_model=DemoSessionResponse,
    responses={403: {"model": ErrorResponse}},
)
async def create_demo_session(
    request: Request,
    body: DemoSessionRequest,
    http_client: httpx.AsyncClient = Depends(get_http_client),
    redis: aioredis.Redis = Depends(get_redis),
) -> DemoSessionResponse:
    settings = get_settings()

    # Fail closed: without a secret we cannot verify the token at all.
    if not settings.turnstile_secret_key:
        raise HTTPException(status_code=403, detail="Turnstile verification unavailable")

    client_ip = _resolve_client_ip(request)

    response = await http_client.post(
        TURNSTILE_VERIFY_URL,
        data={
            "secret": settings.turnstile_secret_key,
            "response": body.token,
            "remoteip": client_ip or "",
        },
    )
    outcome = response.json()
    if not outcome.get("success"):
        raise HTTPException(status_code=403, detail="Turnstile verification failed")

    session_id = secrets.token_urlsafe(32)
    await redis.set(
        f"demo:session:{session_id}",
        client_ip or "",
        ex=settings.demo_session_ttl_seconds,
    )

    return DemoSessionResponse(
        session_id=session_id,
        expires_in=settings.demo_session_ttl_seconds,
    )
