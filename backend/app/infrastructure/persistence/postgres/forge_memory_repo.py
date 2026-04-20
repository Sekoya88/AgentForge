from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.forge_memory import ForgeMemoryChunk
from app.domain.ports.forge_memory_repository import ForgeMemoryRepository
from app.infrastructure.persistence.postgres.models import ForgeUserMemoryModel


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(str(x) for x in v) + "]"


def _to_domain(row: ForgeUserMemoryModel) -> ForgeMemoryChunk:
    return ForgeMemoryChunk(
        id=row.id,
        user_id=row.user_id,
        content=row.content,
        embedding=[],
        source_conv_ids=row.source_conv_ids or [],
        period_start=row.period_start,
        period_end=row.period_end,
        created_at=row.created_at,
    )


class PostgresForgeMemoryRepository(ForgeMemoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def insert(self, chunk: ForgeMemoryChunk) -> ForgeMemoryChunk:
        row = ForgeUserMemoryModel(
            id=uuid4(),
            user_id=chunk.user_id,
            content=chunk.content,
            embedding=chunk.embedding,  # pgvector.sqlalchemy.Vector handles list[float] natively
            source_conv_ids=chunk.source_conv_ids,
            period_start=chunk.period_start,
            period_end=chunk.period_end,
        )
        self._s.add(row)
        await self._s.flush()
        chunk.id = row.id
        return chunk

    async def search_hybrid(
        self,
        user_id: UUID,
        query_text: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[ForgeMemoryChunk]:
        lit = _vec_literal(query_embedding)
        fetch_k = top_k * 4
        result = await self._s.execute(
            text("""
                WITH bm25 AS (
                    SELECT id, content, source_conv_ids, period_start, period_end, created_at,
                           ROW_NUMBER() OVER (
                               ORDER BY ts_rank_cd(
                                   search_vector_tsv,
                                   plainto_tsquery('english', :q)
                               ) DESC
                           ) AS rank
                    FROM forge_user_memories
                    WHERE user_id = :uid
                      AND search_vector_tsv @@ plainto_tsquery('english', :q)
                    LIMIT :fetch_k
                ),
                semantic AS (
                    SELECT id, content, source_conv_ids, period_start, period_end, created_at,
                           ROW_NUMBER() OVER (
                               ORDER BY embedding <=> (:qemb)::vector(1536)
                           ) AS rank
                    FROM forge_user_memories
                    WHERE user_id = :uid
                    LIMIT :fetch_k
                ),
                fused AS (
                    SELECT
                        COALESCE(b.id, s.id)                           AS id,
                        COALESCE(b.content, s.content)                 AS content,
                        COALESCE(b.source_conv_ids, s.source_conv_ids) AS source_conv_ids,
                        COALESCE(b.period_start, s.period_start)       AS period_start,
                        COALESCE(b.period_end, s.period_end)           AS period_end,
                        COALESCE(b.created_at, s.created_at)           AS created_at,
                        -- RRF: BM25 weight=0.4, semantic weight=0.6 (semantic-biased)
                        (COALESCE(0.4 / (60.0 + b.rank), 0) +
                         COALESCE(0.6 / (60.0 + s.rank), 0))           AS rrf_score
                    FROM bm25 b
                    FULL OUTER JOIN semantic s ON b.id = s.id
                )
                SELECT id, content, source_conv_ids, period_start, period_end, created_at
                FROM fused
                ORDER BY rrf_score DESC
                LIMIT :k
            """),
            {"uid": user_id, "q": query_text, "qemb": lit, "fetch_k": fetch_k, "k": top_k},
        )
        rows = result.mappings().all()
        return [
            ForgeMemoryChunk(
                id=r["id"],
                user_id=user_id,
                content=r["content"],
                embedding=[],
                source_conv_ids=r["source_conv_ids"] or [],
                period_start=r["period_start"],
                period_end=r["period_end"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def list_by_user(self, user_id: UUID) -> list[ForgeMemoryChunk]:
        result = await self._s.execute(
            select(ForgeUserMemoryModel)
            .where(ForgeUserMemoryModel.user_id == user_id)
            .order_by(ForgeUserMemoryModel.created_at.desc())
        )
        return [_to_domain(r) for r in result.scalars().all()]

    async def count_by_user(self, user_id: UUID) -> int:
        result = await self._s.execute(
            select(func.count(ForgeUserMemoryModel.id)).where(
                ForgeUserMemoryModel.user_id == user_id
            )
        )
        return result.scalar_one()
