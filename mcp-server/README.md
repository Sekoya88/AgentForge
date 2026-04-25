# AgentForge MCP server

stdio [Model Context Protocol](https://modelcontextprotocol.io) bridge to your AgentForge deployment.

## Setup

```bash
cd mcp-server && uv sync
export AGENTFORGE_API_URL=http://localhost:8000
export AGENTFORGE_TOKEN=<JWT access token>
uv run agentforge-mcp
```

## Tools

- `list_agents` — `GET /api/v1/agents`
- `execute_agent` — `POST /api/v1/agents/{id}/execute` with a single user message

## Cursor / Claude Desktop

Add a stdio server entry pointing at `uv run --directory /path/to/AgentForge/mcp-server agentforge-mcp` with the env vars above.
