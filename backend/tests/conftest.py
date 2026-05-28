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


@pytest.fixture
async def async_client(db_session):
    """
    AsyncClient wired to the test database.

    Overrides the get_db FastAPI dependency so all endpoints in the test
    receive the same AsyncSession as db_session (which points to contextcode_test).
    """
    from httpx import AsyncClient, ASGITransport

    from app.main import app
    from app.models.database import get_db

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=10.0,
    ) as client:
        yield client

    app.dependency_overrides.clear()
