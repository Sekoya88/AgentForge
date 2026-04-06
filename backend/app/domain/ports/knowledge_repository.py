from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class KnowledgeSourceSummary:
    title: str
    chunk_count: int


@dataclass(frozen=True)
class KnowledgeChunkResult:
    content: str
    source_title: str
    rrf_score: float
    chunk_type: str = "paragraph"
    heading_context: str = ""


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
        *,
        chunk_type: str = "paragraph",
        heading_context: str = "",
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

    @abstractmethod
    async def search_hybrid(
        self,
        user_id: UUID,
        query_text: str,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        bm25_weight: float = 0.4,
        semantic_weight: float = 0.6,
        rrf_k: int = 60,
    ) -> list[KnowledgeChunkResult]:
        """Hybrid search: BM25 (ts_vector) + semantic (pgvector) fused with RRF.

        Returns results ordered by descending RRF score, each carrying:
        - content: the raw stored chunk text
        - source_title: document it came from
        - rrf_score: fusion score (higher = more relevant)
        - chunk_type / heading_context: structural metadata
        """
        pass
