"""Tavily web search integration for Forge Assistant tools."""

from __future__ import annotations

import httpx

TAVILY_API_URL = "https://api.tavily.com/search"


async def tavily_search(
    query: str,
    api_key: str,
    *,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = True,
) -> dict:
    """Search the web using Tavily API. Returns results with title, url, content snippets."""
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": include_answer,
        "include_raw_content": False,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(TAVILY_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = []
    if include_answer and data.get("answer"):
        results.append({"type": "answer", "content": data["answer"]})
    for r in data.get("results", []):
        results.append(
            {
                "type": "result",
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:800],
                "score": r.get("score", 0.0),
            }
        )
    return {"query": query, "results": results}
