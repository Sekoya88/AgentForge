"""Red-team campaigns — `/api/v1/campaigns`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class CampaignsAPI:
    """Use via ``client.campaigns``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def launch(
        self,
        agent_id: str | UUID,
        *,
        attack_categories: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"agent_id": str(agent_id)}
        if attack_categories:
            body["attack_categories"] = attack_categories
        if config:
            body.update(config)
        r = await self._client.post("/api/v1/campaigns", json=body)
        r.raise_for_status()
        return r.json()

    async def get(self, campaign_id: str | UUID) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/campaigns/{campaign_id}")
        r.raise_for_status()
        return r.json()

    async def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        r = await self._client.get("/api/v1/campaigns", params={"limit": limit})
        r.raise_for_status()
        return r.json()

    async def report(self, campaign_id: str | UUID) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/campaigns/{campaign_id}/report")
        r.raise_for_status()
        return r.json()

    async def delete(self, campaign_id: str | UUID) -> None:
        r = await self._client.delete(f"/api/v1/campaigns/{campaign_id}")
        r.raise_for_status()
