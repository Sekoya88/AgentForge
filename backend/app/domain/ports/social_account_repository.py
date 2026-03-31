from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class SocialAccountRepository(ABC):
    @abstractmethod
    async def upsert_google(
        self,
        user_id: UUID,
        provider_id: str,
        email: str | None,
        access_token_cipher: str | None,
        refresh_token_cipher: str | None,
        expires_at: datetime | None,
        scopes: list[str] | None = None,
    ) -> None:
        pass
