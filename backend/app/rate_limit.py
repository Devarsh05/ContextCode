"""Rate limiting for the public, auth-less API (slowapi backed by Redis).

The deployed API is public with no auth, so the index/chat endpoints — which
spend OpenAI tokens — are rate limited per client IP. Storage reuses the Redis
broker URL in production; tests point it at ``memory://`` for determinism.
"""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings

# Re-exported so main.py can register the handler without importing slowapi.
__all__ = ["limiter", "build_limiter", "RateLimitExceeded", "rate_limit_handler"]

from slowapi import _rate_limit_exceeded_handler as rate_limit_handler  # noqa: E402


def build_limiter(storage_uri: str, default_limits: list[str] | None = None) -> Limiter:
    """Build a Limiter keyed by client IP.

    ``swallow_errors=True`` makes the limiter fail OPEN: if the storage backend
    (Redis) is briefly unreachable, requests are served rather than 500'd. For an
    auth-less portfolio deploy that's the right trade-off — strict enforcement
    pauses during a Redis outage, which is acceptable.
    """
    return Limiter(
        key_func=get_remote_address,
        storage_uri=storage_uri,
        default_limits=default_limits or [],
        swallow_errors=True,
    )


limiter = build_limiter(get_settings().rate_limit_storage_uri)
