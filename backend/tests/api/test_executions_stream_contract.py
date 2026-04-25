"""Execution SSE route contract (auth + headers)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_execution_stream_requires_auth(client: AsyncClient) -> None:
    aid = uuid.uuid4()
    eid = uuid.uuid4()
    r = await client.get(f"/api/v1/agents/{aid}/stream/{eid}")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_execution_stream_not_found_with_auth(client: AsyncClient) -> None:
    email = f"sse_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "S"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    token = login.json()["access_token"]
    aid = uuid.uuid4()
    eid = uuid.uuid4()
    r = await client.get(
        f"/api/v1/agents/{aid}/stream/{eid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
