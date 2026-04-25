# backend/tests/api/test_finetune_inference_stream.py
import pytest
from httpx import AsyncClient


# Helper: register + login to get auth headers
async def get_auth_headers(client: AsyncClient) -> dict:
    import uuid

    email = f"stream_{uuid.uuid4().hex}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpass123", "name": "Stream"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpass123"},
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
@pytest.mark.skip(reason="Hangs on teardown due to test client connection pool")
async def test_inference_stream_no_modal_url(client: AsyncClient, alembic_ready):

    headers = await get_auth_headers(client)

    # Patch the singleton
    # monkeypatch.setattr(get_settings(), "modal_inference_url", None)

    # MODAL_INFERENCE_URL is not set in test env → should 503
    resp = await client.post(
        "/api/v1/finetune/fake-job-id/inference-stream",
        headers=headers,
        json={"prompt": "hello"},
    )
    assert resp.status_code == 503
