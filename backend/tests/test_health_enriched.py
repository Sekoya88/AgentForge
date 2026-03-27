# backend/tests/test_health_enriched.py
"""Health check tests verifying DB and Redis checks."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok_returns_200_with_checks(client: AsyncClient, alembic_ready):
    """Healthy system returns 200 with all checks passing."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "checks" in body
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["redis"] in ("ok", "unavailable")  # Redis may not be configured


@pytest.mark.asyncio
async def test_health_response_schema(client: AsyncClient, alembic_ready):
    """Response always has status and checks keys."""
    resp = await client.get("/health")
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    assert "db" in body["checks"]
    assert "redis" in body["checks"]
