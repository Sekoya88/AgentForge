import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.social_account_repository import SocialAccountRepository
from app.infrastructure.persistence.postgres.models import SocialAccountModel


class PostgresSocialAccountRepository(SocialAccountRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        scope_val = scopes if scopes is not None else []
        ins = insert(SocialAccountModel).values(
            id=uuid.uuid4(),
            user_id=user_id,
            provider="google",
            provider_id=provider_id,
            email=email,
            access_token_cipher=access_token_cipher,
            refresh_token_cipher=refresh_token_cipher,
            expires_at=expires_at,
            scopes=scope_val,
        )
        ins = ins.on_conflict_do_update(
            index_elements=[SocialAccountModel.provider, SocialAccountModel.provider_id],
            set_={
                "user_id": ins.excluded.user_id,
                "email": ins.excluded.email,
                "access_token_cipher": ins.excluded.access_token_cipher,
                "refresh_token_cipher": ins.excluded.refresh_token_cipher,
                "expires_at": ins.excluded.expires_at,
                "scopes": ins.excluded.scopes,
                "updated_at": func.now(),
            },
        )
        await self._session.execute(ins)
