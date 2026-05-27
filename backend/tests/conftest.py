import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.database import Base

TEST_DATABASE_URL = (
    "postgresql+asyncpg://contextcode:changeme@localhost:5432/contextcode_test"
)


@pytest.fixture
async def db_engine():
    """
    Function-scoped: creates all tables before the test, drops all after.
    Function scope avoids event loop conflicts with asyncio_mode = auto.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Yield an AsyncSession for a single test function."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
