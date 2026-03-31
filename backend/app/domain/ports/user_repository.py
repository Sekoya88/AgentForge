from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.user import User


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        pass

    @abstractmethod
    async def get_credentials_by_email(self, email: str) -> tuple[User, str | None] | None:
        """Return user and password hash if found (hash None for OAuth-only users)."""

    @abstractmethod
    async def get_credentials_by_id(self, user_id: UUID) -> tuple[User, str | None] | None:
        """Return user and password hash if found (hash None for OAuth-only users)."""

    @abstractmethod
    async def update_password(self, user_id: UUID, hashed_password: str) -> None:
        pass

    @abstractmethod
    async def update_collect_speech_examples(self, user_id: UUID, value: bool) -> None:
        pass

    @abstractmethod
    async def save(self, email: str, password_hash: str, display_name: str | None) -> User:
        pass

    @abstractmethod
    async def create_oauth_user(self, email: str, display_name: str | None) -> User:
        """Create user with no password (Google / OAuth sign-in)."""
