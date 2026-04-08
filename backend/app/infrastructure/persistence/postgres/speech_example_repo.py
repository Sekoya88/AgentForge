from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.speech_example import SpeechExample
from app.infrastructure.persistence.postgres.models import SpeechExampleModel


class PostgresSpeechExampleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(m: SpeechExampleModel) -> SpeechExample:
        return SpeechExample(
            id=m.id,
            user_id=m.user_id,
            agent_id=m.agent_id,
            execution_id=m.execution_id,
            audio_b64=m.audio_b64,
            transcription=m.transcription or "",
            score=m.score,
            metadata=dict(m.metadata_ or {}),
            created_at=m.created_at,
            audio_url=m.audio_url,
        )

    async def create(
        self,
        user_id: UUID,
        transcription: str,
        *,
        audio_b64: str | None = None,
        audio_url: str | None = None,
        agent_id: UUID | None = None,
        execution_id: UUID | None = None,
        score: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpeechExample:
        m = SpeechExampleModel(
            user_id=user_id,
            agent_id=agent_id,
            execution_id=execution_id,
            audio_b64=audio_b64,
            audio_url=audio_url,
            transcription=transcription,
            score=score,
            metadata_=metadata or {},
        )
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)
