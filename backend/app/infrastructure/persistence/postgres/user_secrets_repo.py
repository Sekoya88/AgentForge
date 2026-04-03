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
            return {
                "openai_key": None,
                "google_key": None,
                "anthropic_key": None,
                "tavily_key": None,
                "hf_token": None,
                "elevenlabs_key": None,
            }
        return {
            "openai_key": row.encrypted_openai_key,
            "google_key": row.encrypted_google_key,
            "anthropic_key": getattr(row, "encrypted_anthropic_key", None),
            "tavily_key": getattr(row, "encrypted_tavily_key", None),
            "hf_token": getattr(row, "encrypted_hf_token", None),
            "elevenlabs_key": getattr(row, "encrypted_elevenlabs_key", None),
        }

    async def update_secrets(
        self,
        user_id: UUID,
        openai_key: str | None,
        google_key: str | None,
        anthropic_key: str | None = None,
        tavily_key: str | None = None,
        hf_token: str | None = None,
        elevenlabs_key: str | None = None,
    ) -> None:
        values: dict = {
            "user_id": user_id,
            "encrypted_openai_key": openai_key,
            "encrypted_google_key": google_key,
        }
        update_set: dict = {
            "encrypted_openai_key": openai_key,
            "encrypted_google_key": google_key,
            "updated_at": select(func.now()),
        }
        if anthropic_key is not None or hasattr(UserSecretModel, "encrypted_anthropic_key"):
            values["encrypted_anthropic_key"] = anthropic_key
            update_set["encrypted_anthropic_key"] = anthropic_key
        if tavily_key is not None or hasattr(UserSecretModel, "encrypted_tavily_key"):
            values["encrypted_tavily_key"] = tavily_key
            update_set["encrypted_tavily_key"] = tavily_key
        if hf_token is not None or hasattr(UserSecretModel, "encrypted_hf_token"):
            values["encrypted_hf_token"] = hf_token
            update_set["encrypted_hf_token"] = hf_token
        if elevenlabs_key is not None or hasattr(UserSecretModel, "encrypted_elevenlabs_key"):
            values["encrypted_elevenlabs_key"] = elevenlabs_key
            update_set["encrypted_elevenlabs_key"] = elevenlabs_key
        stmt = insert(UserSecretModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_=update_set,
        )
        await self._session.execute(stmt)
        await self._session.flush()
