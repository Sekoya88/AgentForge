# backend/tests/api/test_rate_limiting.py
"""Rate limiting integration tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429_after_threshold(client: AsyncClient, alembic_ready):
    """Hammering /login with bad creds should eventually return 429."""
    payload = {"email": "nobody@example.com", "password": "wrong"}
    responses = []
    for _ in range(25):  # limit is 10/minute on login
        r = await client.post("/api/v1/auth/login", json=payload)
        responses.append(r.status_code)
    assert 429 in responses, f"Expected 429 in {set(responses)}"


@pytest.mark.asyncio
async def test_register_rate_limit_returns_429_after_threshold(client: AsyncClient, alembic_ready):
    """Hammering /register should eventually return 429."""
    responses = []
    for i in range(25):  # limit is 10/minute on register
        r = await client.post(
            "/api/v1/auth/register",
            json={"email": f"spam{i}@example.com", "password": "testpass123"},
        )
        responses.append(r.status_code)
    assert 429 in responses, f"Expected 429 in {set(responses)}"
