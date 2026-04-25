# backend/tests/test_health_enriched.py
"""Health check tests verifying DB and Redis checks."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok_returns_200_with_checks(client: AsyncClient, alembic_ready):
    """200 when DB + Redis are usable; 503 degraded if Redis ping fails after connect."""
    resp = await client.get("/health")
    body = resp.json()
    assert "checks" in body
    assert body["checks"]["db"] == "ok"
    redis = body["checks"]["redis"]
    assert redis in ("ok", "unavailable", "error")
    if redis == "error":
        assert resp.status_code == 503
        assert body["status"] == "degraded"
    else:
        assert resp.status_code == 200
        assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_health_response_schema(client: AsyncClient, alembic_ready):
    """Response always has status and checks keys."""
    resp = await client.get("/health")
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    assert "db" in body["checks"]
    assert "redis" in body["checks"]
