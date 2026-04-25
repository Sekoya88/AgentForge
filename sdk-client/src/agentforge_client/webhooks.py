"""Webhooks CRUD — `/api/v1/webhooks`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class WebhooksAPI:
    """Use via ``client.webhooks``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list(self) -> list[dict[str, Any]]:
        r = await self._client.get("/api/v1/webhooks")
        r.raise_for_status()
        return r.json()

    async def create(
        self,
        *,
        url: str,
        events: list[str] | None = None,
        secret: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"url": url}
        if events:
            body["events"] = events
        if secret:
            body["secret"] = secret
        r = await self._client.post("/api/v1/webhooks", json=body)
        r.raise_for_status()
        return r.json()

    async def update(self, webhook_id: str | UUID, patch: dict[str, Any]) -> dict[str, Any]:
        r = await self._client.patch(f"/api/v1/webhooks/{webhook_id}", json=patch)
        r.raise_for_status()
        return r.json()

    async def delete(self, webhook_id: str | UUID) -> None:
        r = await self._client.delete(f"/api/v1/webhooks/{webhook_id}")
        r.raise_for_status()
