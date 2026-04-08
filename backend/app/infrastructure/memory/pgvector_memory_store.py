"""pgvector-backed MemoryStore implementation."""

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.memory import MemoryEntry
from app.domain.ports.memory_store import MemoryStore
from app.infrastructure.persistence.postgres.models import AgentMemoryModel


def _to_entry(row: AgentMemoryModel) -> MemoryEntry:
    return MemoryEntry(
        id=row.id,
        user_id=row.user_id,
        agent_id=row.agent_id,
        content=row.content,
        importance=row.importance,
        created_at=row.created_at if isinstance(row.created_at, datetime) else datetime.utcnow(),
    )


class PgvectorMemoryStore(MemoryStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        user_id: UUID,
        agent_id: UUID,
        content: str,
        embedding: list[float],
        importance: float = 0.5,
    ) -> MemoryEntry:
        row = AgentMemoryModel(
            id=uuid.uuid4(),
            user_id=user_id,
            agent_id=agent_id,
            content=content,
            embedding=embedding,
            importance=max(0.0, min(1.0, importance)),
        )
        self._session.add(row)
        await self._session.flush()
        return _to_entry(row)

    async def recall(
        self,
        user_id: UUID,
        agent_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
    ) -> list[MemoryEntry]:
        stmt = (
            select(AgentMemoryModel)
            .where(
                AgentMemoryModel.user_id == user_id,
                AgentMemoryModel.agent_id == agent_id,
            )
            .order_by(AgentMemoryModel.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        result = await self._session.execute(stmt)
        return [_to_entry(r) for r in result.scalars().all()]

    async def list_all(
        self,
        user_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        stmt = (
            select(AgentMemoryModel)
            .where(
                AgentMemoryModel.user_id == user_id,
                AgentMemoryModel.agent_id == agent_id,
            )
            .order_by(AgentMemoryModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_to_entry(r) for r in result.scalars().all()]

    async def delete(self, memory_id: UUID, user_id: UUID) -> bool:
        stmt = delete(AgentMemoryModel).where(
            AgentMemoryModel.id == memory_id,
            AgentMemoryModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
