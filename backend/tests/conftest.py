import os

# Keep the rate limiter Redis-free and deterministic in the test suite. Set
# before any app module (which builds the limiter at import) is imported.
os.environ["RATE_LIMIT_STORAGE_URI"] = "memory://"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models.database import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear limiter state between tests so per-route limits don't accumulate
    across the session (memory storage is process-global)."""
    from app.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_session):
    from app.api.cost_gate import require_chat_quota, require_index_quota
    from app.main import app
    from app.models.database import get_db

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # Disable the cost-control gate by default so endpoint tests exercise route
    # logic, not the gate. Overriding the two quota dependencies also bypasses
    # their require_access_code sub-dependency. The dedicated gate tests
    # (test_cost_gate.py) pop these overrides to run the real gate.
    app.dependency_overrides[require_index_quota] = lambda: None
    app.dependency_overrides[require_chat_quota] = lambda: None
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=10.0,
    ) as client:
        yield client
    app.dependency_overrides.clear()
