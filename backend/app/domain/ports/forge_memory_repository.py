from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.forge_memory import ForgeMemoryChunk


class ForgeMemoryRepository(ABC):
    @abstractmethod
    async def insert(self, chunk: ForgeMemoryChunk) -> ForgeMemoryChunk: ...

    @abstractmethod
    async def search_hybrid(
        self,
        user_id: UUID,
        query_text: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[ForgeMemoryChunk]: ...

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[ForgeMemoryChunk]: ...

    @abstractmethod
    async def count_by_user(self, user_id: UUID) -> int: ...
