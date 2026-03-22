import uuid

import pytest

pytestmark = pytest.mark.usefixtures("alembic_ready")


@pytest.mark.asyncio
async def test_knowledge_sources_requires_auth(client) -> None:
    r = await client.get("/api/v1/knowledge/sources")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_knowledge_sources_empty_after_register(client) -> None:
    email = f"k_{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longpassword1", "display_name": "K"},
    )
    access = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "longpassword1"},
        )
    ).json()["access_token"]
    r = await client.get(
        "/api/v1/knowledge/sources",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_knowledge_service_ingest_requires_openai_key() -> None:
    from unittest.mock import MagicMock

    from app.application.services.knowledge_service import KnowledgeService

    settings = MagicMock()
    settings.openai_api_key = None
    svc = KnowledgeService(MagicMock(), settings)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        await svc.ingest_text(uuid.uuid4(), "Doc", "hello")
