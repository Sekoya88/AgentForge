from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.persistence.postgres.models import UserModel


class PostgresUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return self._to_entity(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        q = await self._session.execute(select(UserModel).where(UserModel.email == email))
        row = q.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_credentials_by_email(self, email: str) -> tuple[User, str] | None:
        q = await self._session.execute(select(UserModel).where(UserModel.email == email))
        row = q.scalar_one_or_none()
        if row is None:
            return None
        return (self._to_entity(row), row.hashed_password)

    async def save(self, email: str, password_hash: str, display_name: str | None) -> User:
        m = UserModel(email=email, hashed_password=password_hash, display_name=display_name)
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)

    @staticmethod
    def _to_entity(m: UserModel) -> User:
        return User(
            id=m.id,
            email=m.email,
            display_name=m.display_name,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
