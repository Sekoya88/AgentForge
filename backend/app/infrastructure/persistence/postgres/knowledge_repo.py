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
