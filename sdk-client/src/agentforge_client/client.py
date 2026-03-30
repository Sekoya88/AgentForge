from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import httpx


class AgentforgeClient:
    """Minimal async client for common AgentForge API flows."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        access_token: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._base = (base_url or os.environ.get("AGENTFORGE_API_URL") or "http://localhost:8000").rstrip(
            "/"
        )
        token = access_token or os.environ.get("AGENTFORGE_TOKEN")
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(base_url=self._base, headers=headers, timeout=timeout)

    async def __aenter__(self) -> AgentforgeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_agents(self) -> list[dict[str, Any]]:
        r = await self._client.get("/api/v1/agents")
        r.raise_for_status()
        return r.json()

    async def get_agent(self, agent_id: str | UUID) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/agents/{agent_id}")
        r.raise_for_status()
        return r.json()

    async def create_agent(
        self,
        *,
        name: str,
        graph_definition: dict[str, Any],
        model_config: dict[str, Any],
        description: str | None = None,
        skills: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "graph_definition": graph_definition,
            "model_config": model_config,
        }
        if description is not None:
            body["description"] = description
        if skills is not None:
            body["skills"] = skills
        r = await self._client.post("/api/v1/agents", json=body)
        r.raise_for_status()
        return r.json()

    async def execute_agent(
        self,
        agent_id: str | UUID,
        input_messages: list[dict[str, Any]],
        *,
        run_async: bool = False,
        version: int | None = None,
        alias: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "input_messages": input_messages,
            "run_async": run_async,
        }
        if version is not None:
            body["version"] = version
        if alias is not None:
            body["alias"] = alias
        r = await self._client.post(f"/api/v1/agents/{agent_id}/execute", json=body)
        r.raise_for_status()
        return r.json()

    async def get_execution(
        self, agent_id: str | UUID, execution_id: str | UUID
    ) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/agents/{agent_id}/executions/{execution_id}")
        r.raise_for_status()
        return r.json()
