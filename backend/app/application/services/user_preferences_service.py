from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.entities.user_preferences import UserPreferences
from app.domain.ports.user_preferences_repository import UserPreferencesRepository


def _next_weekday_at_hour(day: int, hour: int, after: datetime) -> datetime:
    """Return next datetime where weekday==day (0=Mon) and hour:00 UTC, strictly after `after`."""
    days_ahead = day - after.weekday()
    if days_ahead < 0 or (days_ahead == 0 and after.hour >= hour):
        days_ahead += 7
    return after.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)


class UserPreferencesService:
    def __init__(self, repo: UserPreferencesRepository) -> None:
        self._repo = repo

    async def get_or_create(self, user_id: UUID) -> UserPreferences:
        prefs = await self._repo.get_by_user_id(user_id)
        if prefs is None:
            prefs = await self._repo.upsert(UserPreferences(user_id=user_id))
        return prefs

    async def update(self, user_id: UUID, **updates) -> UserPreferences:
        prefs = await self.get_or_create(user_id)
        for key, value in updates.items():
            if hasattr(prefs, key) and value is not None:
                setattr(prefs, key, value)
        return await self._repo.upsert(prefs)

    def next_run_at(self, prefs: "UserPreferences") -> datetime:
        return _next_weekday_at_hour(
            prefs.memory_compaction_day, prefs.memory_compaction_hour, datetime.now(UTC)
        )

    def build_forge_context(self, prefs: UserPreferences) -> str | None:
        if not prefs.onboarding_completed:
            return None
        parts: list[str] = []
        if prefs.role:
            parts.append(f"Role: {prefs.role}")
        if prefs.experience_level:
            parts.append(f"Experience level: {prefs.experience_level}")
        if prefs.primary_languages:
            parts.append(f"Primary languages: {', '.join(prefs.primary_languages)}")
        if prefs.use_cases:
            parts.append(f"Main use cases: {', '.join(prefs.use_cases)}")
        if prefs.response_style:
            parts.append(f"Preferred response style: {prefs.response_style}")
        if prefs.custom_context:
            parts.append(f"Additional context: {prefs.custom_context}")
        return "\n".join(parts) if parts else None
