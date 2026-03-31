"""Agent execution schedules (cron) — `/api/v1/agents/{id}/schedules`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class SchedulesAPI:
    """Use via ``client.schedules`` on :class:`AgentforgeClient`."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    def _base(self, agent_id: str | UUID) -> str:
        return f"/api/v1/agents/{agent_id}/schedules"

    async def create(
        self,
        agent_id: str | UUID,
        *,
        cron_expression: str,
        input: dict[str, Any] | None = None,
        alias: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "cron_expression": cron_expression,
            "enabled": enabled,
            "input": input if input is not None else {},
        }
        if alias is not None:
            body["alias"] = alias
        r = await self._client.post(self._base(agent_id), json=body)
        r.raise_for_status()
        return r.json()

    async def list(self, agent_id: str | UUID) -> list[dict[str, Any]]:
        r = await self._client.get(self._base(agent_id))
        r.raise_for_status()
        return r.json()

    async def get(
        self, agent_id: str | UUID, schedule_id: str | UUID
    ) -> dict[str, Any]:
        r = await self._client.get(f"{self._base(agent_id)}/{schedule_id}")
        r.raise_for_status()
        return r.json()

    async def update(
        self,
        agent_id: str | UUID,
        schedule_id: str | UUID,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        """PATCH body; include ``\"alias\": null`` to clear alias (JSON null)."""
        r = await self._client.patch(
            f"{self._base(agent_id)}/{schedule_id}",
            json=patch,
        )
        r.raise_for_status()
        return r.json()

    async def delete(self, agent_id: str | UUID, schedule_id: str | UUID) -> None:
        r = await self._client.delete(f"{self._base(agent_id)}/{schedule_id}")
        r.raise_for_status()
