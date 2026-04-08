"""Forge chat — `/api/v1/forge`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class ForgeAPI:
    """Use via ``client.forge``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def chat(
        self,
        message: str,
        *,
        provider: str = "anthropic",
        model: str | None = None,
        conversation_id: str | UUID | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"message": message, "provider": provider}
        if model:
            body["model"] = model
        if conversation_id:
            body["conversation_id"] = str(conversation_id)
        r = await self._client.post("/api/v1/forge/chat", json=body, timeout=120.0)
        r.raise_for_status()
        return r.json()

    async def list_conversations(self) -> list[dict[str, Any]]:
        r = await self._client.get("/api/v1/forge/conversations")
        r.raise_for_status()
        return r.json()

    async def get_conversation(self, conversation_id: str | UUID) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/forge/conversations/{conversation_id}")
        r.raise_for_status()
        return r.json()

    async def delete_conversation(self, conversation_id: str | UUID) -> None:
        r = await self._client.delete(f"/api/v1/forge/conversations/{conversation_id}")
        r.raise_for_status()
