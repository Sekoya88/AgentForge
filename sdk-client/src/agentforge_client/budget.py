"""Agent budget endpoints — `/api/v1/agents/{agent_id}/budget`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class BudgetAPI:
    """Use via ``client.budget``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get(self, agent_id: str | UUID) -> dict[str, Any]:
        """Return the 30-day rolling spend and budget status for an agent."""
        r = await self._client.get(f"/api/v1/agents/{agent_id}/budget")
        r.raise_for_status()
        return r.json()

    async def set(
        self,
        agent_id: str | UUID,
        *,
        limit_usd: float | None = None,
        alert_threshold: float = 0.8,
    ) -> dict[str, Any]:
        """Set or clear the budget limit and alert threshold for an agent."""
        body: dict[str, Any] = {"alert_threshold": alert_threshold}
        if limit_usd is not None:
            body["limit_usd"] = limit_usd
        r = await self._client.put(f"/api/v1/agents/{agent_id}/budget", json=body)
        r.raise_for_status()
        return r.json()
