# backend/tests/api/test_finetune_inference_stream.py
import pytest
from httpx import AsyncClient


# Helper: register + login to get auth headers
async def get_auth_headers(client: AsyncClient) -> dict:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "stream@test.com", "password": "testpass123", "name": "Stream"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "stream@test.com", "password": "testpass123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_inference_stream_missing_prompt(client: AsyncClient, alembic_ready):
    headers = await get_auth_headers(client)
    resp = await client.post(
        "/api/v1/finetune/fake-job-id/inference-stream",
        headers=headers,
        json={},  # missing prompt
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_inference_stream_no_modal_url(client: AsyncClient, alembic_ready):
    from app.config import Settings
    from app.dependencies import get_settings_dep
    from app.main import app

    # Override settings to simulate no modal_inference_url
    def _override_settings():
        s = Settings()
        s.modal_inference_url = None
        return s

    app.dependency_overrides[get_settings_dep] = _override_settings

    headers = await get_auth_headers(client)
    # MODAL_INFERENCE_URL is not set in test env → should 503
    try:
        resp = await client.post(
            "/api/v1/finetune/fake-job-id/inference-stream",
            headers=headers,
            json={"prompt": "hello"},
        )
        assert resp.status_code == 503
    finally:
        app.dependency_overrides.pop(get_settings_dep, None)
