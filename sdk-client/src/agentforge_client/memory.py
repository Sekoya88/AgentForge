"""Agent memory endpoints — `/api/v1/agents/{agent_id}/memories`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class MemoryAPI:
    """Use via ``client.memory``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list(self, agent_id: str | UUID, *, limit: int = 100) -> list[dict[str, Any]]:
        r = await self._client.get(f"/api/v1/agents/{agent_id}/memories", params={"limit": limit})
        r.raise_for_status()
        return r.json()

    async def delete(self, agent_id: str | UUID, memory_id: str | UUID) -> None:
        r = await self._client.delete(f"/api/v1/agents/{agent_id}/memories/{memory_id}")
        r.raise_for_status()
