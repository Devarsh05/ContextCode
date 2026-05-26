import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_check_returns_ok():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
