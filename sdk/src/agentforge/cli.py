"""AgentForge SDK CLI: validate exports, run locally, pull from API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from langchain_core.messages import HumanMessage

from agentforge.agent import LocalAgent, load_agent
from agentforge.graph_validate import parse_and_validate_graph


def _cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.file)
    raw = json.loads(path.read_text(encoding="utf-8"))
    gd = raw.get("graph_definition")
    if not gd:
        print("error: missing graph_definition", file=sys.stderr)
        return 1
    try:
        parse_and_validate_graph(gd)
    except Exception as e:
        print(f"validation failed: {e}", file=sys.stderr)
        return 1
    print("ok: graph_definition is valid")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.file)
    raw = json.loads(path.read_text(encoding="utf-8"))
    agent = load_agent(raw)
    import asyncio

    msg = args.message or "Hello"
    result = asyncio.run(agent.ainvoke({"messages": [HumanMessage(content=msg)]}))
    msgs = result.get("messages") or []
    if msgs:
        print(getattr(msgs[-1], "content", msgs[-1]))
    return 0


def _cmd_pull(args: argparse.Namespace) -> int:
    base = os.environ.get("AGENTFORGE_API_URL", "http://localhost:8000").rstrip("/")
    token = os.environ.get("AGENTFORGE_TOKEN")
    if not token:
        print("error: set AGENTFORGE_TOKEN (Bearer access token)", file=sys.stderr)
        return 1
    url = f"{base}/api/v1/agents/{args.agent_id}/export"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"pull failed: {e}", file=sys.stderr)
        return 1
    out = Path(args.output)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    return 0


def _cmd_push(args: argparse.Namespace) -> int:
    base = os.environ.get("AGENTFORGE_API_URL", "http://localhost:8000").rstrip("/")
    token = os.environ.get("AGENTFORGE_TOKEN")
    if not token:
        print("error: set AGENTFORGE_TOKEN (Bearer access token)", file=sys.stderr)
        return 1
    path = Path(args.file)
    try:
        export_data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"error reading file: {e}", file=sys.stderr)
        return 1
    if args.name:
        export_data["name_override"] = args.name
    body = json.dumps(export_data).encode()
    url = f"{base}/api/v1/agents/import"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"push failed: {e}", file=sys.stderr)
        return 1
    agent_id = data.get("id", "<unknown>")
    print(f"Agent pushed successfully. ID: {agent_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentforge", description="AgentForge SDK utilities"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser(
        "validate", help="Validate graph_definition in an export JSON"
    )
    p_val.add_argument("file", help="Path to agent export JSON")
    p_val.set_defaults(func=_cmd_validate)

    p_run = sub.add_parser("run", help="Run an export JSON locally via LocalAgent")
    p_run.add_argument("file", help="Path to agent export JSON")
    p_run.add_argument(
        "-m",
        "--message",
        default="Hello",
        help="User message (default: Hello)",
    )
    p_run.set_defaults(func=_cmd_run)

    p_pull = sub.add_parser(
        "pull", help="Download agent export from API (needs AGENTFORGE_TOKEN)"
    )
    p_pull.add_argument("agent_id", help="Agent UUID")
    p_pull.add_argument(
        "-o",
        "--output",
        default="agent_export.json",
        help="Output file path",
    )
    p_pull.set_defaults(func=_cmd_pull)

    p_push = sub.add_parser(
        "push", help="Upload agent export JSON to API (needs AGENTFORGE_TOKEN)"
    )
    p_push.add_argument("file", help="Path to agent export JSON")
    p_push.add_argument(
        "-n",
        "--name",
        default=None,
        help="Override agent name on import",
    )
    p_push.set_defaults(func=_cmd_push)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
