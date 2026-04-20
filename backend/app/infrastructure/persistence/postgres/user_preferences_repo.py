from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user_preferences import UserPreferences
from app.domain.ports.user_preferences_repository import UserPreferencesRepository
from app.infrastructure.persistence.postgres.models import UserPreferencesModel


class PostgresUserPreferencesRepository(UserPreferencesRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        result = await self._session.execute(
            select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def upsert(self, prefs: UserPreferences) -> UserPreferences:
        stmt = (
            pg_insert(UserPreferencesModel)
            .values(
                user_id=prefs.user_id,
                onboarding_completed=prefs.onboarding_completed,
                role=prefs.role,
                experience_level=prefs.experience_level,
                primary_languages=prefs.primary_languages,
                use_cases=prefs.use_cases,
                response_style=prefs.response_style,
                custom_context=prefs.custom_context,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "onboarding_completed": prefs.onboarding_completed,
                    "role": prefs.role,
                    "experience_level": prefs.experience_level,
                    "primary_languages": prefs.primary_languages,
                    "use_cases": prefs.use_cases,
                    "response_style": prefs.response_style,
                    "custom_context": prefs.custom_context,
                },
            )
            .returning(UserPreferencesModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        return self._to_domain(row)

    def _to_domain(self, row: UserPreferencesModel) -> UserPreferences:
        return UserPreferences(
            user_id=row.user_id,
            onboarding_completed=row.onboarding_completed,
            role=row.role,
            experience_level=row.experience_level,
            primary_languages=list(row.primary_languages or []),
            use_cases=list(row.use_cases or []),
            response_style=row.response_style,
            custom_context=row.custom_context,
        )
