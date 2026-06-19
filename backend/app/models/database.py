import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()


# ── URL scheme normalization ──────────────────────────────────────────────────
# DATABASE_URL arrives in different shapes depending on the host: locally it is
# the async form (postgresql+asyncpg://), Railway injects the sync form
# (postgresql://), and some providers use the legacy postgres:// scheme. The
# async engine needs an async driver and the sync engine / Alembic need a sync
# driver, so derive both from the one raw value. Both helpers are idempotent and
# leave non-Postgres URLs (e.g. SQLite in tests) untouched.


def to_async_url(url: str) -> str:
    """Return ``url`` with the postgresql+asyncpg driver (no double-convert)."""
    u = make_url(url)
    if u.get_backend_name() in ("postgres", "postgresql"):
        return u.set(drivername="postgresql+asyncpg").render_as_string(
            hide_password=False
        )
    return url


def to_sync_url(url: str) -> str:
    """Return ``url`` with the postgresql+psycopg2 driver (no double-convert)."""
    u = make_url(url)
    if u.get_backend_name() in ("postgres", "postgresql"):
        return u.set(drivername="postgresql+psycopg2").render_as_string(
            hide_password=False
        )
    return url


# Raw env value — read contract preserved; async_url / sync_url derive from it.
DATABASE_URL: str = os.environ["DATABASE_URL"]

# ── Async engine — used by FastAPI endpoints ──────────────────────────────────
engine = create_async_engine(to_async_url(DATABASE_URL), echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Sync engine — used by Celery worker tasks (no running event loop) ─────────
SYNC_DATABASE_URL: str = to_sync_url(DATABASE_URL)

sync_engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)

SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
