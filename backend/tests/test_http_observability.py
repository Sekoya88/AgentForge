"""Correlation ID header and access-log paths (health stays quiet)."""

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_correlation_id_echoed_on_api_route(client) -> None:
    cid = f"test-{uuid.uuid4().hex[:12]}"
    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid", "X-Correlation-ID": cid},
    )
    assert r.status_code == 401
    assert r.headers.get("X-Correlation-ID") == cid


@pytest.mark.asyncio
async def test_correlation_id_generated_when_absent(client) -> None:
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
    assert r.status_code == 401
    out = r.headers.get("X-Correlation-ID")
    assert out and len(out) >= 8
