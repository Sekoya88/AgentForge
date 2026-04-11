"""MemoryStore that does nothing — for tests or when pgvector is intentionally off."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.domain.entities.memory import MemoryEntry
from app.domain.ports.memory_store import MemoryStore


class NoopMemoryStore(MemoryStore):
    async def save(
        self,
        user_id: UUID,
        agent_id: UUID,
        content: str,
        embedding: list[float],
        importance: float = 0.5,
    ) -> MemoryEntry:
        return MemoryEntry(
            id=uuid.uuid4(),
            user_id=user_id,
            agent_id=agent_id,
            content=content,
            importance=importance,
            created_at=datetime.now(UTC),
        )

    async def recall(
        self,
        user_id: UUID,
        agent_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
    ) -> list[MemoryEntry]:
        return []

    async def list_all(
        self,
        user_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        return []

    async def delete(self, memory_id: UUID, user_id: UUID) -> bool:
        return False
