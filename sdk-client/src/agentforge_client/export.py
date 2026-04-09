"""Agent export endpoint — `/api/v1/agents/{agent_id}/export`."""

from __future__ import annotations

from uuid import UUID

import httpx


class ExportAPI:
    """Use via ``client.export``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def python(self, agent_id: str | UUID) -> str:
        """Export agent as a standalone Python script (returns source code string)."""
        r = await self._client.get(f"/api/v1/agents/{agent_id}/export", params={"format": "python"})
        r.raise_for_status()
        return r.text

    async def docker(self, agent_id: str | UUID) -> bytes:
        """Export agent as a Docker zip archive (returns raw bytes)."""
        r = await self._client.get(f"/api/v1/agents/{agent_id}/export", params={"format": "docker"})
        r.raise_for_status()
        return r.content

    async def langgraph(self, agent_id: str | UUID) -> dict:
        """Export agent as a LangGraph JSON definition."""
        r = await self._client.get(f"/api/v1/agents/{agent_id}/export", params={"format": "langgraph"})
        r.raise_for_status()
        return r.json()
