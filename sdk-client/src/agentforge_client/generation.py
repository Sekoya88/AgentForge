"""AI generation — `/api/v1/generation`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class GenerationAPI:
    """Use via ``client.generation``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def generate_agent(
        self,
        description: str,
        *,
        provider: str = "anthropic",
    ) -> dict[str, Any]:
        body = {"description": description, "provider": provider}
        r = await self._client.post("/api/v1/generation/agent", json=body, timeout=120.0)
        r.raise_for_status()
        return r.json()

    async def generate_skill(
        self,
        description: str,
        *,
        provider: str = "anthropic",
    ) -> dict[str, Any]:
        body = {"description": description, "provider": provider}
        r = await self._client.post("/api/v1/generation/skill", json=body, timeout=120.0)
        r.raise_for_status()
        return r.json()
