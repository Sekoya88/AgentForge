from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.user_secrets_repository import UserSecretsDict, UserSecretsRepository
from app.infrastructure.persistence.postgres.models import UserSecretModel


class PostgresUserSecretsRepository(UserSecretsRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_secrets(self, user_id: UUID) -> UserSecretsDict:
        stmt = select(UserSecretModel).where(UserSecretModel.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return {"openai_key": None, "google_key": None}
        return {
            "openai_key": row.encrypted_openai_key,
            "google_key": row.encrypted_google_key,
        }

    async def update_secrets(
        self, user_id: UUID, openai_key: str | None, google_key: str | None
    ) -> None:
        stmt = insert(UserSecretModel).values(
            user_id=user_id,
            encrypted_openai_key=openai_key,
            encrypted_google_key=google_key,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "encrypted_openai_key": stmt.excluded.encrypted_openai_key,
                "encrypted_google_key": stmt.excluded.encrypted_google_key,
                "updated_at": select(func.now()),
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
