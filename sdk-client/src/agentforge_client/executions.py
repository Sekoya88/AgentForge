"""Executions — `/api/v1/agents/{id}/executions`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class ExecutionsAPI:
    """Use via ``client.executions``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list(
        self,
        agent_id: str | UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        r = await self._client.get(
            f"/api/v1/agents/{agent_id}/executions",
            params={"limit": limit, "offset": offset},
        )
        r.raise_for_status()
        return r.json()

    async def get(self, agent_id: str | UUID, execution_id: str | UUID) -> dict[str, Any]:
        r = await self._client.get(
            f"/api/v1/agents/{agent_id}/executions/{execution_id}"
        )
        r.raise_for_status()
        return r.json()

    async def feedback(
        self,
        agent_id: str | UUID,
        execution_id: str | UUID,
        *,
        score: float,
        comment: str = "",
    ) -> dict[str, Any]:
        body = {"score": score, "comment": comment}
        r = await self._client.post(
            f"/api/v1/agents/{agent_id}/executions/{execution_id}/feedback", json=body
        )
        r.raise_for_status()
        return r.json()

    async def interrupt(
        self,
        agent_id: str | UUID,
        execution_id: str | UUID,
        decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        r = await self._client.post(
            f"/api/v1/agents/{agent_id}/executions/{execution_id}/resume",
            json={"decisions": decisions},
        )
        r.raise_for_status()
        return r.json()
