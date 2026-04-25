"""Fine-tuning jobs — `/api/v1/finetune`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class FinetuneAPI:
    """Use via ``client.finetune``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def create(
        self,
        *,
        agent_id: str | UUID | None = None,
        base_model: str,
        modality: str = "text_sft",
        dataset_path: str | None = None,
        hyperparams: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"base_model": base_model, "modality": modality}
        if agent_id:
            body["agent_id"] = str(agent_id)
        if dataset_path:
            body["dataset_path"] = dataset_path
        if hyperparams:
            body["hyperparams"] = hyperparams
        r = await self._client.post("/api/v1/finetune", json=body)
        r.raise_for_status()
        return r.json()

    async def get(self, job_id: str | UUID) -> dict[str, Any]:
        r = await self._client.get(f"/api/v1/finetune/{job_id}")
        r.raise_for_status()
        return r.json()

    async def list(self) -> list[dict[str, Any]]:
        r = await self._client.get("/api/v1/finetune")
        r.raise_for_status()
        return r.json()

    async def deploy(self, job_id: str | UUID) -> dict[str, Any]:
        r = await self._client.post(f"/api/v1/finetune/{job_id}/deploy", json={})
        r.raise_for_status()
        return r.json()

    async def trigger(self, job_id: str | UUID) -> dict[str, Any]:
        r = await self._client.post(f"/api/v1/finetune/{job_id}/trigger", json={})
        r.raise_for_status()
        return r.json()
