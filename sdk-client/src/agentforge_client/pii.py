"""PII masking endpoint — `/api/v1/pii/mask`."""

from __future__ import annotations

from typing import Any

import httpx


class PiiAPI:
    """Use via ``client.pii``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def mask(self, text: str) -> dict[str, Any]:
        """Mask PII patterns in *text*.

        Returns ``{"masked_text": str, "hit_count": int}``.
        """
        r = await self._client.post("/api/v1/pii/mask", json={"text": text})
        r.raise_for_status()
        return r.json()

    async def mask_messages(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Mask PII in a list of ``{role, content}`` message dicts."""
        r = await self._client.post("/api/v1/pii/mask", json={"messages": messages})
        r.raise_for_status()
        return r.json()
