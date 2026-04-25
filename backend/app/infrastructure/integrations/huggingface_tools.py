"""HuggingFace Hub search tools — used by the Forge assistant.

Uses the public HuggingFace API (https://huggingface.co/api/).
Optionally honours an ``HF_TOKEN`` for higher rate limits and private models.
"""

from __future__ import annotations

import httpx

_HF_API = "https://huggingface.co/api"
_TIMEOUT = 30.0


def _headers(hf_token: str | None = None) -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json"}
    if hf_token:
        h["Authorization"] = f"Bearer {hf_token}"
    return h


async def hf_search_models(
    query: str,
    *,
    task: str | None = None,
    library: str | None = None,
    limit: int = 10,
    hf_token: str | None = None,
) -> list[dict]:
    """Search HuggingFace Hub for models matching *query*.

    Returns a list of dicts with: id, author, downloads, likes, pipeline_tag, tags.
    """
    params: dict[str, str | int] = {"search": query, "limit": min(limit, 30), "sort": "downloads"}
    if task:
        params["pipeline_tag"] = task
    if library:
        params["library"] = library

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_HF_API}/models", params=params, headers=_headers(hf_token))
        r.raise_for_status()

    results = []
    for m in r.json():
        results.append(
            {
                "id": m.get("id", ""),
                "author": m.get("author", ""),
                "downloads": m.get("downloads", 0),
                "likes": m.get("likes", 0),
                "pipeline_tag": m.get("pipeline_tag", ""),
                "tags": (m.get("tags") or [])[:10],
                "last_modified": m.get("lastModified", ""),
            }
        )
    return results


async def hf_search_datasets(
    query: str,
    *,
    limit: int = 10,
    hf_token: str | None = None,
) -> list[dict]:
    """Search HuggingFace Hub for datasets matching *query*."""
    params: dict[str, str | int] = {"search": query, "limit": min(limit, 30), "sort": "downloads"}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_HF_API}/datasets", params=params, headers=_headers(hf_token))
        r.raise_for_status()

    results = []
    for d in r.json():
        results.append(
            {
                "id": d.get("id", ""),
                "author": d.get("author", ""),
                "downloads": d.get("downloads", 0),
                "likes": d.get("likes", 0),
                "tags": (d.get("tags") or [])[:10],
                "description": (d.get("description") or "")[:200],
                "last_modified": d.get("lastModified", ""),
            }
        )
    return results


async def hf_model_info(
    model_id: str,
    *,
    hf_token: str | None = None,
) -> dict:
    """Get detailed info about a specific HuggingFace model."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(
            f"{_HF_API}/models/{model_id}",
            headers=_headers(hf_token),
        )
        r.raise_for_status()

    m = r.json()
    # Extract key fields, keep response compact
    siblings = m.get("siblings") or []
    files = [s.get("rfilename", "") for s in siblings[:20]]

    return {
        "id": m.get("id", ""),
        "author": m.get("author", ""),
        "pipeline_tag": m.get("pipeline_tag", ""),
        "tags": m.get("tags") or [],
        "downloads": m.get("downloads", 0),
        "likes": m.get("likes", 0),
        "library_name": m.get("library_name", ""),
        "model_type": m.get("config", {}).get("model_type", ""),
        "license": _extract_license(m),
        "card_data": {
            "language": (m.get("cardData") or {}).get("language"),
            "datasets": (m.get("cardData") or {}).get("datasets"),
            "base_model": (m.get("cardData") or {}).get("base_model"),
        },
        "files": files,
        "created_at": m.get("createdAt", ""),
        "last_modified": m.get("lastModified", ""),
        "safetensors": bool(m.get("safetensors")),
        "private": m.get("private", False),
    }


def _extract_license(model: dict) -> str:
    """Best-effort license extraction."""
    card = model.get("cardData") or {}
    if card.get("license"):
        return str(card["license"])
    tags = model.get("tags") or []
    for t in tags:
        if t.startswith("license:"):
            return t.split(":", 1)[1]
    return ""
