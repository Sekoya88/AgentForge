import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient, alembic_ready) -> None:
    """Use shared ASGI client so lifespan wires Redis before /health runs."""
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
