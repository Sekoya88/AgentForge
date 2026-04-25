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


# ---------------------------------------------------------------------------
# Agents CRUD
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_agent(
    name: str,
    graph_definition_json: str,
    model_config_json: str = "{}",
    description: str = "",
) -> str:
    """Create a new agent. graph_definition_json and model_config_json must be valid JSON strings."""
    body = {
        "name": name,
        "description": description,
        "graph_definition": json.loads(graph_definition_json),
        "llm_model_config": json.loads(model_config_json),
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/agents", json=body, headers=_headers(), timeout=60.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def update_agent(agent_id: str, patch_json: str) -> str:
    """Update an agent. patch_json is a JSON string with fields to update (name, description, graph_definition, llm_model_config, status, etc.)."""
    body = json.loads(patch_json)
    async with httpx.AsyncClient() as client:
        r = await client.put(
            f"{_BASE}/api/v1/agents/{agent_id}",
            json=body,
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def delete_agent(agent_id: str) -> str:
    """Delete an agent by ID. Returns empty string on success (204 No Content)."""
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            f"{_BASE}/api/v1/agents/{agent_id}", headers=_headers(), timeout=60.0
        )
        r.raise_for_status()
        return json.dumps({"deleted": True, "agent_id": agent_id})


@mcp.tool()
async def export_agent(agent_id: str, format: str = "python") -> str:
    """Export an agent in the given format: python, docker, or langgraph. Returns the raw content as a string."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/agents/{agent_id}/export",
            params={"format": format},
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "application/json" in content_type:
            return json.dumps(r.json(), indent=2)
        return r.text


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_agent_memories(agent_id: str, limit: int = 100) -> str:
    """List memories stored for a specific agent."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/agents/{agent_id}/memories",
            params={"limit": limit},
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def delete_agent_memory(agent_id: str, memory_id: str) -> str:
    """Delete a specific memory entry for an agent."""
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            f"{_BASE}/api/v1/agents/{agent_id}/memories/{memory_id}",
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps({"deleted": True, "memory_id": memory_id})


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_webhooks() -> str:
    """List all registered webhooks for the authenticated user."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_BASE}/api/v1/webhooks", headers=_headers(), timeout=60.0)
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def create_webhook(url: str, events_json: str, secret: str = "") -> str:
    """Create a webhook endpoint. events_json is a JSON array of event names (e.g. '[\"execution.completed\"]'). Allowed events: execution.completed, campaign.completed."""
    body: dict = {"url": url, "events": json.loads(events_json)}
    if secret:
        body["secret"] = secret
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/webhooks", json=body, headers=_headers(), timeout=60.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_agent_budget(agent_id: str) -> str:
    """Get the 30-day rolling spend and budget status for an agent."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/agents/{agent_id}/budget", headers=_headers(), timeout=60.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def set_agent_budget(
    agent_id: str, limit_usd: float | None = None, alert_threshold: float = 0.8
) -> str:
    """Set or clear the budget limit (USD) and alert threshold (0.0–1.0) for an agent. Pass limit_usd=None to clear the budget."""
    body: dict = {"alert_threshold": alert_threshold}
    if limit_usd is not None:
        body["limit_usd"] = limit_usd
    async with httpx.AsyncClient() as client:
        r = await client.put(
            f"{_BASE}/api/v1/agents/{agent_id}/budget",
            json=body,
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Fine-tuning
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_finetune_jobs() -> str:
    """List all fine-tuning jobs for the authenticated user."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_BASE}/api/v1/finetune", headers=_headers(), timeout=60.0)
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def create_finetune_job(
    agent_id: str,
    modality: str = "text_sft",
    provider: str = "modal",
) -> str:
    """Trigger an automatic fine-tuning job for an agent. modality must be text_sft, whisper, or tts_voice."""
    body = {"agent_id": agent_id, "base_model": provider, "min_score": 0.7}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/finetune/trigger", json=body, headers=_headers(), timeout=60.0
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_execution_metrics(days: int = 7, agent_id: str = "") -> str:
    """Get daily execution metrics (counts, latency, tokens, cost) for the past N days. Optionally filter by agent_id."""
    params: dict = {"days": days}
    if agent_id:
        params["agent_id"] = agent_id
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/dashboard/metrics",
            params=params,
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def list_all_executions(limit: int = 50, offset: int = 0) -> str:
    """List all executions across all agents with pagination."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/dashboard/executions",
            params={"limit": limit, "offset": offset},
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_agent_schedules(agent_id: str) -> str:
    """List all cron schedules configured for an agent."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE}/api/v1/agents/{agent_id}/schedules",
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def create_agent_schedule(
    agent_id: str, cron_expr: str, payload_json: str = "{}"
) -> str:
    """Create a cron schedule for an agent. cron_expr is a standard cron expression (e.g. '0 9 * * 1'). payload_json is the input passed to the agent on each trigger."""
    body = {
        "cron_expression": cron_expr,
        "input": json.loads(payload_json),
        "enabled": True,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/api/v1/agents/{agent_id}/schedules",
            json=body,
            headers=_headers(),
            timeout=60.0,
        )
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
