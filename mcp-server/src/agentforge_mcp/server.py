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


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_agents() -> str:
    """List all agents for the authenticated user."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_BASE}/api/v1/agents", headers=_headers(), timeout=60.0)
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def get_agent(agent_id: str) -> str:
    """Get a single agent by ID."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_BASE}/api/v1/agents/{agent_id}", headers=_headers(), timeout=60.0)
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


# ---------------------------------------------------------------------------
# Executions
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_executions(agent_id: str, limit: int = 10) -> str:
    """List recent executions for an agent."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/agents/{agent_id}/executions",
            params={"limit": limit},
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def get_execution(agent_id: str, execution_id: str) -> str:
    """Get a specific execution by ID."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/agents/{agent_id}/executions/{execution_id}",
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_skills() -> str:
    """List all custom skills for the authenticated user."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_BASE}/api/v1/skills", headers=_headers(), timeout=60.0)
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def create_skill(name: str, source_code: str, description: str = "") -> str:
    """Create a new Python skill."""
    body = {"name": name, "source_code": source_code, "description": description}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/skills", json=body, headers=_headers(), timeout=60.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_knowledge(query: str, top_k: int = 5) -> str:
    """Semantic search over the user's knowledge base."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/knowledge/search",
            params={"q": query, "top_k": top_k},
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def ingest_knowledge(text: str, source_title: str) -> str:
    """Ingest raw text into the knowledge base."""
    body = {"title": source_title, "text": text}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/knowledge/ingest", json=body, headers=_headers(), timeout=120.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def ingest_knowledge_url(url: str) -> str:
    """Fetch a URL and ingest its content into the knowledge base."""
    body = {"url": url}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/knowledge/ingest-url", json=body, headers=_headers(), timeout=120.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------


@mcp.tool()
async def launch_campaign(agent_id: str, attack_categories: list[str] | None = None) -> str:
    """Launch a red-team campaign against an agent."""
    body: dict = {"agent_id": agent_id}
    if attack_categories:
        body["attack_categories"] = attack_categories
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/campaigns", json=body, headers=_headers(), timeout=60.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def get_campaign_report(campaign_id: str) -> str:
    """Get the report for a completed campaign."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/campaigns/{campaign_id}", headers=_headers(), timeout=60.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Forge
# ---------------------------------------------------------------------------


@mcp.tool()
async def forge_chat(message: str, provider: str = "anthropic", model: str = "") -> str:
    """Send a message to Forge (direct LLM chat with tools)."""
    body: dict = {"message": message, "provider": provider}
    if model:
        body["model"] = model
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/forge/chat", json=body, headers=_headers(), timeout=120.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_conversation(agent_id: str) -> str:
    """Create a new conversation thread for an agent."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/agents/{agent_id}/conversations",
            json={},
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def get_conversation_messages(agent_id: str, conversation_id: str) -> str:
    """List messages in a conversation thread."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/agents/{agent_id}/conversations/{conversation_id}/messages",
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
