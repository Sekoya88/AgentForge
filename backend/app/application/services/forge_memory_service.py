from __future__ import annotations

import logging
from uuid import UUID

import anthropic
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.forge_memory import ForgeMemoryChunk
from app.domain.ports.forge_memory_repository import ForgeMemoryRepository
from app.infrastructure.persistence.postgres.models import ForgeExecutionModel

log = logging.getLogger(__name__)

_COMPACTION_PROMPT = """\
You are building a long-term memory entry for an AI assistant.

Given a conversation transcript between a user and an AI assistant, extract and summarize:
1. The user's technical background, programming languages, and expertise areas
2. Projects they are working on (names, tech stack, purpose)
3. Coding preferences, patterns, and conventions they favor
4. Recurring topics or problems they face
5. Decisions made and their reasoning
6. Things they explicitly liked or disliked about the AI's responses

Write a single concise paragraph (150-250 words) in third person. Be specific and concrete.
Example: "User is building a customer support agent using Python + LangGraph for an e-commerce \
platform. Prefers concise code without over-engineering. Working with PostgreSQL + pgvector for \
RAG. Uses Anthropic Claude as the LLM provider. Frustrated by overly verbose explanations."

TRANSCRIPT:
{transcript}

SUMMARY:"""


def _build_transcript(executions: list) -> str:
    lines: list[str] = []
    for exe in executions:
        for msg in exe.input_messages or []:
            content = msg.get("content", "")
            if msg.get("role") == "user" and isinstance(content, str):
                lines.append(f"User: {content[:500]}")
        for msg in exe.output_messages or []:
            content = msg.get("content", "")
            if msg.get("role") == "assistant" and isinstance(content, str):
                lines.append(f"Assistant: {content[:500]}")
    return "\n".join(lines[:60])


def _format_memory_context(chunks: list[ForgeMemoryChunk]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        period = chunk.period_start.strftime("%Y-%m") if chunk.period_start else "?"
        parts.append(f"[Memory from {period}] {chunk.content}")
    return "\n\n".join(parts)


async def _embed(text: str, openai_key: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {openai_key}"},
            json={"model": "text-embedding-3-small", "input": text},
        )
        r.raise_for_status()
        return list(r.json()["data"][0]["embedding"])


async def _summarize(transcript: str, anthropic_key: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=anthropic_key)
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": _COMPACTION_PROMPT.format(transcript=transcript)}],
    )
    return msg.content[0].text.strip()


class ForgeMemoryService:
    def __init__(self, repo: ForgeMemoryRepository, session: AsyncSession) -> None:
        self._repo = repo
        self._session = session

    async def compact(
        self,
        user_id: UUID,
        openai_key: str,
        anthropic_key: str,
    ) -> int:
        """Summarize uncompacted forge conversations into memory chunks. Returns count created."""
        result = await self._session.execute(
            select(ForgeExecutionModel)
            .where(
                ForgeExecutionModel.user_id == user_id,
                ForgeExecutionModel.status == "completed",
                ForgeExecutionModel.memory_compacted.is_(False),
            )
            .order_by(ForgeExecutionModel.started_at.asc())
        )
        executions = list(result.scalars().all())
        if not executions:
            return 0

        by_conv: dict[str, list] = {}
        for exe in executions:
            key = str(exe.conversation_id)
            by_conv.setdefault(key, []).append(exe)

        count = 0
        all_exe_ids: list[UUID] = []

        for conv_exes in by_conv.values():
            transcript = _build_transcript(conv_exes)
            if not transcript.strip():
                continue

            period_start = conv_exes[0].started_at
            period_end = conv_exes[-1].completed_at or conv_exes[-1].started_at

            try:
                summary = await _summarize(transcript, anthropic_key)
                embedding = await _embed(summary, openai_key)
                chunk = ForgeMemoryChunk(
                    user_id=user_id,
                    content=summary,
                    embedding=embedding,
                    source_conv_ids=[str(exe.conversation_id) for exe in conv_exes],
                    period_start=period_start,
                    period_end=period_end,
                )
                await self._repo.insert(chunk)
            except Exception:
                log.exception("forge_memory_compaction_failed", extra={"user_id": str(user_id)})
                continue

            all_exe_ids.extend(exe.id for exe in conv_exes)
            count += 1

        if all_exe_ids:
            await self._session.execute(
                update(ForgeExecutionModel)
                .where(ForgeExecutionModel.id.in_(all_exe_ids))
                .values(memory_compacted=True)
                .execution_options(synchronize_session="fetch")
            )

        return count

    async def retrieve_context(
        self,
        user_id: UUID,
        query: str,
        openai_key: str,
        top_k: int = 4,
    ) -> str | None:
        """Retrieve top-K relevant memory chunks for a user query.

        Returns formatted string or None.
        """
        memory_count = await self._repo.count_by_user(user_id)
        if memory_count == 0:
            return None

        try:
            embedding = await _embed(query, openai_key)
        except Exception:
            log.warning("forge_memory_embed_failed", extra={"user_id": str(user_id)})
            return None

        chunks = await self._repo.search_hybrid(user_id, query, embedding, top_k=top_k)
        if not chunks:
            return None

        return _format_memory_context(chunks)
