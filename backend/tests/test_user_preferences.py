import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
