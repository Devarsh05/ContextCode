"""Centralized application configuration.

All deploy-facing environment variables live here as a single pydantic-settings
schema. Settings reads ``os.environ`` directly (no ``env_file``) so it composes
with the ``load_dotenv()`` calls already made in ``main.py`` / ``database.py``.

``get_settings()`` returns a fresh instance per call (it is deliberately NOT
cached) so tests that ``patch.dict(os.environ, ...)`` see their changes — matching
the existing env-patch style in the embedder tests.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # ── Connection URLs ───────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://contextcode:changeme@localhost:5432/contextcode"
    redis_url: str = "redis://localhost:6379/0"

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    # When chroma_host is set, the client factory returns an HttpClient (the API
    # and worker then share one Chroma server). Empty → embedded PersistentClient.
    chroma_host: str = ""
    chroma_port: int = 8000
    chroma_token: str = ""
    chroma_persist_path: str = "./chroma_data"

    # ── Embeddings / LLM ──────────────────────────────────────────────────────
    embedding_provider: str = "local"  # "local" (MiniLM, dev) | "openai" (prod)
    openai_api_key: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_allow_origins: str = "http://localhost:3000"

    # ── Rate limiting (slowapi) ───────────────────────────────────────────────
    rate_limit_index: str = "10/hour"
    rate_limit_chat: str = "30/minute"
    # Defaults to redis_url (resolved below) so the limiter reuses the broker.
    rate_limit_storage_uri: str = ""

    # ── Cost-control gate ─────────────────────────────────────────────────────
    # Shared secret required (X-Access-Code header) on the two token-spending
    # endpoints. Empty ⇒ the gate rejects every request with 401.
    access_code: str = ""
    # Global daily ceilings (keyed by UTC date in Redis, auto-reset). Tunable on
    # Railway without a redeploy.
    quota_index_daily: int = 3
    quota_chat_daily: int = 50
    # Per-counter TTL (~25h) so the daily key self-expires even if traffic stops.
    quota_ttl_seconds: int = 90000

    # ── Demo session (Cloudflare Turnstile) ───────────────────────────────────
    # Server-side Turnstile secret. Empty ⇒ POST /demo/session rejects every
    # request (fail closed, same posture as access_code).
    turnstile_secret_key: str = ""
    # Lifetime of a minted demo session id in Redis.
    demo_session_ttl_seconds: int = 3600

    @model_validator(mode="after")
    def _default_storage_to_redis(self) -> "Settings":
        if not self.rate_limit_storage_uri:
            self.rate_limit_storage_uri = self.redis_url
        return self

    @property
    def cors_origins(self) -> list[str]:
        """CORS_ALLOW_ORIGINS as a trimmed, non-empty list."""
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    """Return a fresh Settings instance (reads os.environ at call time)."""
    return Settings()
