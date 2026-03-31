"""Tests for voice sample upload and list."""

import io
import uuid

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    email = f"vs_{uuid.uuid4().hex}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpass123", "name": "VS"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_voice_samples_upload_and_list(client: AsyncClient, alembic_ready):
    headers = await _register_and_login(client)
    files = {"file": ("clip.webm", io.BytesIO(b"fake-audio-bytes"), "audio/webm")}
    data = {"label": "my voice"}
    r = await client.post(
        "/api/v1/speech/voice-samples",
        headers=headers,
        files=files,
        data=data,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["label"] == "my voice"
    assert body["audio_bytes"] > 0
    assert "id" in body

    r2 = await client.get("/api/v1/speech/voice-samples", headers=headers)
    assert r2.status_code == 200
    items = r2.json()
    assert len(items) == 1
    assert items[0]["id"] == body["id"]
    assert items[0]["audio_bytes"] == body["audio_bytes"]
    assert "audio_b64" not in items[0]


@pytest.mark.asyncio
async def test_speech_deployed_auth_and_empty_list(client: AsyncClient, alembic_ready):
    resp = await client.get("/api/v1/speech/deployed")
    assert resp.status_code == 401

    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/speech/deployed", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []
