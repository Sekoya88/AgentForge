"""Prompt optimizer endpoints — `/api/v1/prompt-optimizer`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class PromptOptimizerAPI:
    """Use via ``client.prompt_optimizer``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def start(
        self,
        agent_id: str | UUID,
        test_input: str,
        *,
        num_variants: int = 3,
        judge_criteria: str = "helpfulness, conciseness, factual accuracy",
    ) -> dict[str, Any]:
        """Submit an optimization job. Returns ``{"job_id": str, "status": "pending"}``."""
        body = {
            "agent_id": str(agent_id),
            "test_input": test_input,
            "num_variants": num_variants,
            "judge_criteria": judge_criteria,
        }
        r = await self._client.post("/api/v1/prompt-optimizer", json=body)
        r.raise_for_status()
        return r.json()

    async def get(self, job_id: str) -> dict[str, Any]:
        """Poll the result of an optimization job."""
        r = await self._client.get(f"/api/v1/prompt-optimizer/{job_id}")
        r.raise_for_status()
        return r.json()
