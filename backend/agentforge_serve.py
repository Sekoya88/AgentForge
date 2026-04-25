"""agentforge_serve.py — Standalone agent runtime.

Usage:
    python agentforge_serve.py serve agent.json [--port 8080] [--host 0.0.0.0]

Loads an AgentForge Graph (AFG) JSON file and exposes a minimal HTTP API:
    POST /chat    {"message": "string"} -> {"response": "string"}
    GET  /health  -> {"status": "ok", "agent": "<name>"}

No database or Redis required — in-memory only.
Requires OPENAI_API_KEY or ANTHROPIC_API_KEY in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------


def _find_first_llm_node(graph: dict[str, Any]) -> dict[str, Any] | None:
    """Return the config dict of the first node with type 'llm'."""
    entry_id: str = graph.get("entry_point", "")
    nodes: list[dict[str, Any]] = graph.get("nodes", [])

    # Prefer entry-point node if it is an LLM node.
    for node in nodes:
        if node.get("id") == entry_id and node.get("type", "llm") == "llm":
            return node.get("config", {})

    # Fall back to first LLM node found.
    for node in nodes:
        if node.get("type", "llm") == "llm":
            return node.get("config", {})

    return None


def _system_prompt(node_config: dict[str, Any]) -> str:
    """Extract system prompt from a node config, with a sensible default."""
    return (
        node_config.get("system_prompt")
        or node_config.get("systemPrompt")
        or node_config.get("instructions")
        or "You are a helpful assistant."
    )


# ---------------------------------------------------------------------------
# LLM call (OpenAI or Anthropic, whichever key is present)
# ---------------------------------------------------------------------------


def _call_llm(system: str, user_message: str) -> str:
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if openai_key:
        from openai import OpenAI  # already in pyproject.toml

        client = OpenAI(api_key=openai_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        )
        return resp.choices[0].message.content or ""

    if anthropic_key:
        import anthropic  # already in pyproject.toml (langchain-anthropic pulls it)

        client = anthropic.Anthropic(api_key=anthropic_key)
        resp = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return resp.content[0].text if resp.content else ""

    raise RuntimeError("No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


class HealthResponse(BaseModel):
    status: str
    agent: str


def build_app(agent_file: Path) -> FastAPI:
    raw = json.loads(agent_file.read_text())

    # Accept either a bare graph or a full agent JSON with graph_definition wrapper.
    if "graph_definition" in raw:
        graph = raw["graph_definition"]
        agent_name: str = raw.get("name", agent_file.stem)
    elif "nodes" in raw:
        graph = raw
        agent_name = agent_file.stem
    else:
        raise ValueError(f"{agent_file} does not contain 'graph_definition' or 'nodes' key.")

    node_config = _find_first_llm_node(graph) or {}
    system = _system_prompt(node_config)

    app = FastAPI(title="AgentForge Serve", version="1.0.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", agent=agent_name)

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest) -> ChatResponse:
        if not req.message.strip():
            raise HTTPException(status_code=400, detail="message must not be empty")
        try:
            text = _call_llm(system, req.message)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return ChatResponse(response=text)

    return app


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agentforge_serve",
        description="Run an AgentForge agent from a JSON file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Start the agent HTTP server.")
    serve.add_argument("agent_file", type=Path, help="Path to the AFG JSON file.")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")

    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()

    if args.command == "serve":
        agent_path: Path = args.agent_file.expanduser().resolve()
        if not agent_path.exists():
            print(f"Error: file not found: {agent_path}", file=sys.stderr)
            sys.exit(1)

        try:
            app = build_app(agent_path)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"Error loading agent: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"AgentForge Serve — agent: {agent_path.name}")
        print(f"Listening on http://{args.host}:{args.port}")
        print('  POST /chat   {"message": "..."}')
        print("  GET  /health")
        uvicorn.run(app, host=args.host, port=args.port)
