from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.knowledge_repository import KnowledgeRepository, KnowledgeSourceSummary


def _vec_literal(values: list[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in values) + "]"


class PostgresKnowledgeRepository(KnowledgeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_chunk(
        self,
        user_id: UUID,
        chunk_id: UUID,
        source_title: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
    ) -> None:
        lit = _vec_literal(embedding)
        await self._session.execute(
            text(
                """
                INSERT INTO knowledge_chunks
                    (id, user_id, source_title, chunk_index, content, embedding)
                VALUES
                    (:id, :user_id, :source_title, :chunk_index, :content, CAST(:emb AS vector))
                """
            ),
            {
                "id": chunk_id,
                "user_id": user_id,
                "source_title": source_title[:512],
                "chunk_index": chunk_index,
                "content": content,
                "emb": lit,
            },
        )

    async def delete_by_title(self, user_id: UUID, source_title: str) -> int:
        r = await self._session.execute(
            text(
                """
                DELETE FROM knowledge_chunks
                WHERE user_id = :user_id AND source_title = :title
                """
            ),
            {"user_id": user_id, "title": source_title},
        )
        return r.rowcount or 0

    async def list_sources(self, user_id: UUID) -> list[KnowledgeSourceSummary]:
        r = await self._session.execute(
            text(
                """
                SELECT source_title, COUNT(*) AS n
                FROM knowledge_chunks
                WHERE user_id = :user_id
                GROUP BY source_title
                ORDER BY source_title
                """
            ),
            {"user_id": user_id},
        )
        rows = r.mappings().all()
        return [
            KnowledgeSourceSummary(title=str(row["source_title"]), chunk_count=int(row["n"]))
            for row in rows
        ]

    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int,
    ) -> list[str]:
        lit = _vec_literal(query_embedding)
        r = await self._session.execute(
            text(
                """
                SELECT content
                FROM knowledge_chunks
                WHERE user_id = :user_id
                ORDER BY embedding <=> CAST(:qemb AS vector)
                LIMIT :k
                """
            ),
            {"user_id": user_id, "qemb": lit, "k": top_k},
        )
        return [str(row[0]) for row in r.fetchall()]

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
    ) -> list[str]:
        lit = _vec_literal(query_embedding)
        # We fetch 4x top_k from both strategies before fusion
        r = await self._session.execute(
            text(
                """
                WITH bm25 AS (
                    SELECT id, content,
                           ROW_NUMBER() OVER (
                               ORDER BY ts_rank_cd(
                                   search_vector, plainto_tsquery('english', :q)
                               ) DESC
                           ) AS rank
                    FROM knowledge_chunks
                    WHERE user_id = :uid AND search_vector @@ plainto_tsquery('english', :q)
                    LIMIT :fetch_k
                ),
                semantic AS (
                    SELECT id, content,
                           ROW_NUMBER() OVER (ORDER BY embedding <=> CAST(:qemb AS vector)) AS rank
                    FROM knowledge_chunks
                    WHERE user_id = :uid
                    LIMIT :fetch_k
                ),
                fused AS (
                    SELECT COALESCE(b.id, s.id) AS id,
                           COALESCE(b.content, s.content) AS content,
                           (COALESCE(:bm25_w / (:rrf_k + b.rank), 0) +
                            COALESCE(:sem_w / (:rrf_k + s.rank), 0)) AS rrf_score
                    FROM bm25 b
                    FULL OUTER JOIN semantic s ON b.id = s.id
                )
                SELECT content
                FROM fused
                ORDER BY rrf_score DESC
                LIMIT :k
                """
            ),
            {
                "uid": user_id,
                "q": query_text,
                "qemb": lit,
                "fetch_k": top_k * 4,
                "k": top_k,
                "bm25_w": bm25_weight,
                "sem_w": semantic_weight,
                "rrf_k": rrf_k,
            },
        )
        return [str(row[0]) for row in r.fetchall()]
