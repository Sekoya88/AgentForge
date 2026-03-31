from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.voice_sample import VoiceSample
from app.infrastructure.persistence.postgres.models import VoiceSampleModel


class PostgresVoiceSampleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(m: VoiceSampleModel) -> VoiceSample:
        return VoiceSample(
            id=m.id,
            user_id=m.user_id,
            label=m.label,
            audio_b64=m.audio_b64,
            metadata=dict(m.metadata_ or {}),
            created_at=m.created_at,
        )

    async def create(
        self,
        user_id: UUID,
        audio_b64: str,
        *,
        label: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> VoiceSample:
        m = VoiceSampleModel(
            user_id=user_id,
            label=label,
            audio_b64=audio_b64,
            metadata_=metadata or {},
        )
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)

    async def list_for_user(self, user_id: UUID, *, limit: int = 100) -> list[VoiceSample]:
        q = await self._session.execute(
            select(VoiceSampleModel)
            .where(VoiceSampleModel.user_id == user_id)
            .order_by(VoiceSampleModel.created_at.desc())
            .limit(min(limit, 200))
        )
        return [self._to_entity(r) for r in q.scalars().all()]
