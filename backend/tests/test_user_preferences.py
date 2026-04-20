import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.user_preferences_service import UserPreferencesService
from app.domain.entities.user_preferences import UserPreferences
from app.infrastructure.persistence.postgres.models import UserPreferencesModel
from app.infrastructure.persistence.postgres.user_preferences_repo import (
    PostgresUserPreferencesRepository,
)


def test_user_preferences_model_importable():
    assert UserPreferencesModel.__tablename__ == "user_preferences"


@pytest.mark.asyncio
async def test_upsert_and_get(db_session: AsyncSession, alembic_ready):
    user_id = uuid.uuid4()
    repo = PostgresUserPreferencesRepository(db_session)

    # Row does not exist yet
    result = await repo.get_by_user_id(user_id)
    assert result is None

    # Insert
    prefs = UserPreferences(
        user_id=user_id,
        role="developer",
        experience_level="expert",
        primary_languages=["Python", "TypeScript"],
        use_cases=["Build agents"],
        response_style="concise",
    )
    saved = await repo.upsert(prefs)
    assert saved.role == "developer"
    assert saved.primary_languages == ["Python", "TypeScript"]

    # Retrieve
    fetched = await repo.get_by_user_id(user_id)
    assert fetched is not None
    assert fetched.role == "developer"

    # Update (upsert again)
    prefs.role = "ml_engineer"
    updated = await repo.upsert(prefs)
    assert updated.role == "ml_engineer"


@pytest.mark.asyncio
async def test_get_or_create_returns_defaults_when_not_found():
    repo = AsyncMock()
    repo.get_by_user_id.return_value = None
    repo.upsert.return_value = UserPreferences(user_id=uuid.uuid4())
    svc = UserPreferencesService(repo)

    result = await svc.get_or_create(uuid.uuid4())
    repo.upsert.assert_called_once()
    assert result.onboarding_completed is False


def test_build_forge_context_returns_none_when_not_completed():
    prefs = UserPreferences(user_id=uuid.uuid4(), onboarding_completed=False, role="dev")
    svc = UserPreferencesService(AsyncMock())
    assert svc.build_forge_context(prefs) is None


def test_build_forge_context_builds_string():
    prefs = UserPreferences(
        user_id=uuid.uuid4(),
        onboarding_completed=True,
        role="ML Engineer",
        experience_level="expert",
        primary_languages=["Python"],
        use_cases=["Build agents", "Fine-tune models"],
        response_style="concise",
        custom_context="Working on LLM-powered search at a startup.",
    )
    svc = UserPreferencesService(AsyncMock())
    ctx = svc.build_forge_context(prefs)
    assert ctx is not None
    assert "ML Engineer" in ctx
    assert "expert" in ctx
    assert "Python" in ctx
    assert "concise" in ctx
    assert "Working on LLM-powered search" in ctx


@pytest.mark.asyncio
async def test_get_preferences_creates_defaults(client: AsyncClient, alembic_ready):
    email = f"pref_{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Test1234!", "display_name": "Test"},
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/user-preferences", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["onboarding_completed"] is False
    assert data["role"] is None


@pytest.mark.asyncio
async def test_update_preferences(client: AsyncClient, alembic_ready):
    email = f"pref2_{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Test1234!", "display_name": "Test"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.put(
        "/api/v1/user-preferences",
        headers=headers,
        json={
            "role": "developer",
            "experience_level": "expert",
            "primary_languages": ["Python", "TypeScript"],
            "use_cases": ["Build agents"],
            "response_style": "concise",
            "onboarding_completed": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "developer"
    assert data["onboarding_completed"] is True
    assert "Python" in data["primary_languages"]
