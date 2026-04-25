"""Auth registration flag tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_register_blocked_when_disabled(client: AsyncClient) -> None:
    """Registration returns 403 when ALLOW_REGISTRATION=false."""
    from app.config import Settings
    from app.dependencies import get_settings_dep
    from app.main import app

    app.dependency_overrides[get_settings_dep] = lambda: Settings(ALLOW_REGISTRATION=False)
    try:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "blocked@test.com",
                "password": "Password123!",
                "display_name": "Blocked",
            },
        )
    finally:
        app.dependency_overrides.pop(get_settings_dep, None)

    assert resp.status_code == 403
    assert "registration" in resp.json()["detail"].lower()
