"""Knowledge base — `/api/v1/knowledge`."""

from __future__ import annotations

from typing import Any

import httpx


class KnowledgeAPI:
    """Use via ``client.knowledge``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list_sources(self) -> list[dict[str, Any]]:
        r = await self._client.get("/api/v1/knowledge/sources")
        r.raise_for_status()
        return r.json()

    async def ingest(self, *, title: str, text: str) -> dict[str, Any]:
        r = await self._client.post(
            "/api/v1/knowledge/ingest", json={"title": title, "text": text}
        )
        r.raise_for_status()
        return r.json()

    async def ingest_url(self, url: str) -> dict[str, Any]:
        r = await self._client.post("/api/v1/knowledge/ingest-url", json={"url": url})
        r.raise_for_status()
        return r.json()

    async def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        r = await self._client.get(
            "/api/v1/knowledge/search", params={"q": query, "top_k": top_k}
        )
        r.raise_for_status()
        return r.json()

    async def delete(self, title: str) -> None:
        r = await self._client.delete(f"/api/v1/knowledge/sources/{title}")
        r.raise_for_status()
