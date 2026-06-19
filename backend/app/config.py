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
