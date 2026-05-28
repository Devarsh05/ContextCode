import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL: str = os.environ["DATABASE_URL"]

# ── Async engine — used by FastAPI endpoints ──────────────────────────────────
engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Sync engine — used by Celery worker tasks (no running event loop) ─────────
# Derived from DATABASE_URL by swapping asyncpg driver for psycopg2.
SYNC_DATABASE_URL: str = DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)

sync_engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)

SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
