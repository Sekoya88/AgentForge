"""Skills CRUD — `/api/v1/skills`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class SkillsAPI:
    """Use via ``client.skills``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list(self) -> list[dict[str, Any]]:
        r = await self._client.get("/api/v1/skills")
        r.raise_for_status()
        return r.json()

    async def get(self, skill_id: str | UUID) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/skills/{skill_id}")
        r.raise_for_status()
        return r.json()

    async def create(
        self,
        *,
        name: str,
        source_code: str,
        description: str = "",
    ) -> dict[str, Any]:
        body = {"name": name, "source_code": source_code, "description": description}
        r = await self._client.post("/api/v1/skills", json=body)
        r.raise_for_status()
        return r.json()

    async def update(
        self,
        skill_id: str | UUID,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        r = await self._client.patch(f"/api/v1/skills/{skill_id}", json=patch)
        r.raise_for_status()
        return r.json()

    async def delete(self, skill_id: str | UUID) -> None:
        r = await self._client.delete(f"/api/v1/skills/{skill_id}")
        r.raise_for_status()
