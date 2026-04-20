from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.user_preferences import UserPreferences


class UserPreferencesRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> UserPreferences | None: ...

    @abstractmethod
    async def upsert(self, prefs: UserPreferences) -> UserPreferences: ...
