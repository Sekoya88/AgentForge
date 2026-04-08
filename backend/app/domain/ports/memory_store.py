from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.memory import MemoryEntry


class MemoryStore(ABC):
    """Port for persistent cross-session agent memory backed by vector search."""

    @abstractmethod
    async def save(
        self,
        user_id: UUID,
        agent_id: UUID,
        content: str,
        embedding: list[float],
        importance: float = 0.5,
    ) -> MemoryEntry:
        """Persist a memory entry and return it."""

    @abstractmethod
    async def recall(
        self,
        user_id: UUID,
        agent_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
    ) -> list[MemoryEntry]:
        """Return the top_k most semantically relevant memories."""

    @abstractmethod
    async def list_all(
        self,
        user_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """Return all memories for a (user, agent) pair, newest first."""

    @abstractmethod
    async def delete(self, memory_id: UUID, user_id: UUID) -> bool:
        """Delete a memory. Returns True if found and deleted."""
