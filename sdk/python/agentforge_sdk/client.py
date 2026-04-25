"""AgentForge Python SDK — embed agents in any project."""
from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import httpx

from .models import Agent, Conversation, ExecutionResult


class AgentsAPI:
    def __init__(self, http: httpx.Client, base_url: str) -> None:
        self._http = http
        self._base = base_url

    def list(self) -> list[Agent]:
        """List all agents for the authenticated user."""
        resp = self._http.get(f"{self._base}/api/v1/agents")
        resp.raise_for_status()
        return [
            Agent(id=a["id"], name=a["name"], description=a.get("description"), status=a.get("status", "draft"))
            for a in resp.json()
        ]

    def run(self, agent_id: str, message: str, thread_id: str | None = None) -> ExecutionResult:
        """Run an agent synchronously and return the result."""
        resp = self._http.post(
            f"{self._base}/api/v1/agents/{agent_id}/execute",
            json={
                "input_messages": [{"role": "user", "content": message}],
                "thread_id": thread_id,
                "run_async": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        output_msgs = data.get("output_messages", [])
        output_text = output_msgs[-1]["content"] if output_msgs else ""
        return ExecutionResult(
            id=data["id"],
            status=data["status"],
            output=output_text,
            token_usage=data.get("token_usage", {}),
            duration_ms=data.get("duration_ms"),
        )

    def stream(self, agent_id: str, message: str, thread_id: str | None = None) -> Generator[str, None, None]:
        """
        Stream agent response token by token.

        Usage:
            for token in client.agents.stream(agent_id, "Hello"):
                print(token, end="", flush=True)
        """
        # Start async execution
        resp = self._http.post(
            f"{self._base}/api/v1/agents/{agent_id}/execute",
            json={
                "input_messages": [{"role": "user", "content": message}],
                "thread_id": thread_id,
                "run_async": True,
            },
        )
        resp.raise_for_status()
        execution_id = resp.json()["id"]

        # Stream SSE
        with self._http.stream(
            "GET",
            f"{self._base}/api/v1/agents/{agent_id}/stream/{execution_id}",
        ) as stream_resp:
            for line in stream_resp.iter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "token":
                            yield data.get("content", "")
                        elif data.get("type") in ("done", "error"):
                            break
                    except json.JSONDecodeError:
                        continue

    def export(self, agent_id: str) -> dict[str, Any]:
        """Export agent as a portable JSON bundle."""
        resp = self._http.get(f"{self._base}/api/v1/agents/{agent_id}/export")
        resp.raise_for_status()
        return resp.json()

    def import_bundle(self, bundle: dict[str, Any]) -> Agent:
        """Import an agent from a JSON bundle. Returns the new agent."""
        resp = self._http.post(f"{self._base}/api/v1/agents/import", json=bundle)
        resp.raise_for_status()
        a = resp.json()
        return Agent(id=a["id"], name=a["name"], description=a.get("description"), status=a.get("status", "draft"))


class ConversationsAPI:
    def __init__(self, http: httpx.Client, base_url: str) -> None:
        self._http = http
        self._base = base_url

    def create(self, agent_id: str, title: str | None = None) -> Conversation:
        """Create a new conversation for an agent."""
        resp = self._http.post(
            f"{self._base}/api/v1/agents/{agent_id}/conversations",
            json={"title": title},
        )
        resp.raise_for_status()
        c = resp.json()
        return Conversation(id=c["id"], agent_id=c["agent_id"], thread_id=c["thread_id"],
                           title=c.get("title"), message_count=c.get("message_count", 0))

    def list(self, agent_id: str) -> list[Conversation]:
        """List conversations for an agent."""
        resp = self._http.get(f"{self._base}/api/v1/agents/{agent_id}/conversations")
        resp.raise_for_status()
        return [
            Conversation(id=c["id"], agent_id=c["agent_id"], thread_id=c["thread_id"],
                        title=c.get("title"), message_count=c.get("message_count", 0))
            for c in resp.json()
        ]


class AgentForgeClient:
    """
    AgentForge Python SDK client.

    Usage:
        from agentforge_sdk import AgentForgeClient

        client = AgentForgeClient(
            base_url="https://your-agentforge.com",
            api_key="your-api-key",
        )

        # Run an agent
        result = client.agents.run(agent_id="...", message="Hello!")
        print(result.output)

        # Stream tokens
        for token in client.agents.stream(agent_id="...", message="Tell me a story"):
            print(token, end="", flush=True)

        # With persistent conversation
        conv = client.conversations.create(agent_id="...")
        result = client.agents.run(agent_id="...", message="Hello", thread_id=conv.thread_id)
        result2 = client.agents.run(agent_id="...", message="Follow up", thread_id=conv.thread_id)
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self.agents = AgentsAPI(self._http, self.base_url)
        self.conversations = ConversationsAPI(self._http, self.base_url)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "AgentForgeClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
