from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class KnowledgeSourceSummary:
    title: str
    chunk_count: int


class KnowledgeRepository(ABC):
    @abstractmethod
    async def insert_chunk(
        self,
        user_id: UUID,
        chunk_id: UUID,
        source_title: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
    ) -> None:
        pass

    @abstractmethod
    async def delete_by_title(self, user_id: UUID, source_title: str) -> int:
        """Returns number of rows deleted."""

    @abstractmethod
    async def list_sources(self, user_id: UUID) -> list[KnowledgeSourceSummary]:
        pass

    @abstractmethod
    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int,
    ) -> list[str]:
        pass
