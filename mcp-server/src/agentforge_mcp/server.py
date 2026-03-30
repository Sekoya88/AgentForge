"""stdio MCP server — thin proxy to AgentForge API v1."""

from __future__ import annotations

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AgentForge")

_BASE = os.environ.get("AGENTFORGE_API_URL", "http://localhost:8000").rstrip("/")
_TOKEN = os.environ.get("AGENTFORGE_TOKEN", "")


def _headers() -> dict[str, str]:
    h = {"Accept": "application/json", "Content-Type": "application/json"}
    if _TOKEN:
        h["Authorization"] = f"Bearer {_TOKEN}"
    return h


@mcp.tool()
async def list_agents() -> str:
    """List all agents for the authenticated user."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_BASE}/api/v1/agents", headers=_headers(), timeout=60.0)
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def execute_agent(agent_id: str, user_message: str, run_async: bool = False) -> str:
    """Run an agent with one user message (sync by default)."""
    body = {
        "input_messages": [{"role": "user", "content": user_message}],
        "run_async": run_async,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/agents/{agent_id}/execute",
            json=body,
            headers=_headers(),
            timeout=120.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
