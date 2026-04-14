"""Auth registration flag tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_register_blocked_when_disabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Registration returns 403 when ALLOW_REGISTRATION=false."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "allow_registration", False)
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "blocked@test.com",
            "password": "Password123!",
            "display_name": "Blocked",
        },
    )
    assert resp.status_code == 403
    assert "registration" in resp.json()["detail"].lower()
