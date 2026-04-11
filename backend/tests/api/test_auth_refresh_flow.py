"""Auth login + refresh + 401 without token."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(client: AsyncClient) -> None:
    email = f"refresh_{uuid.uuid4().hex[:8]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "R"},
    )
    assert reg.status_code in (200, 201), reg.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "longpassword1"},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    refresh = body["refresh_token"]
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]
    assert r.json()["refresh_token"] == refresh


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
