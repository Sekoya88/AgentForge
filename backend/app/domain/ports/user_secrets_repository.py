from abc import ABC, abstractmethod
from typing import TypedDict
from uuid import UUID


class UserSecretsDict(TypedDict):
    openai_key: str | None
    google_key: str | None


class UserSecretsRepository(ABC):
    @abstractmethod
    async def get_secrets(self, user_id: UUID) -> UserSecretsDict:
        pass

    @abstractmethod
    async def update_secrets(
        self, user_id: UUID, openai_key: str | None, google_key: str | None
    ) -> None:
        pass
