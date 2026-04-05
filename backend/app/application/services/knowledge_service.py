import uuid
from typing import Any
from uuid import UUID

import httpx

from app.application.services.secrets_service import SecretsService
from app.config import Settings
from app.domain.ports.knowledge_repository import KnowledgeRepository, KnowledgeSourceSummary


def chunk_text(text: str, *, max_chars: int = 1000, overlap: int = 120) -> list[str]:
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [t]
    chunks: list[str] = []
    start = 0
    while start < len(t):
        end = min(start + max_chars, len(t))
        chunks.append(t[start:end])
        if end >= len(t):
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


async def _embed_batch(texts: list[str], api_key: str) -> list[list[float]]:
    if not texts:
        return []
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "text-embedding-3-small", "input": texts},
            timeout=120.0,
        )
        r.raise_for_status()
        data = r.json()
    out: list[list[float]] = []
    for item in sorted(data["data"], key=lambda x: x["index"]):
        out.append(list(item["embedding"]))
    return out


async def _embed_one(text: str, api_key: str) -> list[float]:
    vecs = await _embed_batch([text], api_key)
    return vecs[0]


class KnowledgeService:
    def __init__(
        self, repo: KnowledgeRepository, settings: Settings, secrets: SecretsService
    ) -> None:
        self._repo = repo
        self._settings = settings
        self._secrets = secrets

    async def ingest_text(self, user_id: UUID, title: str, text: str) -> dict[str, Any]:
        user_secrets = await self._secrets.get_decrypted_secrets(user_id)
        key = user_secrets.get("openai_key") or self._settings.openai_api_key
        if not key:
            raise ValueError("OPENAI_API_KEY is required to index knowledge. Set it in Settings.")
        title = (title or "untitled").strip()[:512]
        parts = chunk_text(text)
        if not parts:
            await self._repo.delete_by_title(user_id, title)
            return {"title": title, "chunks": 0}
        await self._repo.delete_by_title(user_id, title)
        embeddings = await _embed_batch(parts, key)
        for i, (chunk, emb) in enumerate(zip(parts, embeddings, strict=True)):
            await self._repo.insert_chunk(
                user_id,
                uuid.uuid4(),
                title,
                i,
                chunk,
                emb,
            )
        return {"title": title, "chunks": len(parts)}

    async def list_sources(self, user_id: UUID) -> list[KnowledgeSourceSummary]:
        return await self._repo.list_sources(user_id)

    async def delete_source(self, user_id: UUID, title: str) -> int:
        return await self._repo.delete_by_title(user_id, title)

    async def search_context(self, user_id: UUID, query: str, top_k: int = 5) -> str:
        user_secrets = await self._secrets.get_decrypted_secrets(user_id)
        key = user_secrets.get("openai_key") or self._settings.openai_api_key
        if not key:
            return "(Knowledge search unavailable: OPENAI_API_KEY not set.)"
        q = (query or "").strip()
        if not q:
            return "(empty query)"
        emb = await _embed_one(q, key)
        chunks = await self._repo.search_hybrid(user_id, q, emb, top_k=top_k)
        if not chunks:
            return "(no matching documents in your knowledge base; ingest text under Knowledge.)"
        return "\n\n---\n\n".join(chunks)
