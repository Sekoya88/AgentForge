# agentforge-client

Async HTTP client for [AgentForge](https://github.com/) REST API `v1`. Complements the **runtime** package [`agentforge`](../sdk/) (local LangGraph execution from exports).

## Install

```bash
pip install -e ./sdk-client
```

## Usage

```python
import asyncio
from agentforge_client import AgentforgeClient

async def main():
    async with AgentforgeClient(
        base_url="http://localhost:8000",
        access_token="YOUR_JWT",
    ) as client:
        agents = await client.list_agents()
        ex = await client.execute_agent(
            agents[0]["id"],
            [{"role": "user", "content": "Hello"}],
            run_async=False,
        )
        print(ex.get("status"), ex.get("output_messages"))

asyncio.run(main())
```

Environment variables (optional defaults):

- `AGENTFORGE_API_URL` — base URL (default `http://localhost:8000`)
- `AGENTFORGE_TOKEN` — Bearer access token

## Regenerate OpenAPI snapshot

From repo root:

```bash
cd backend && uv run python ../scripts/export_openapi.py
```

The schema is written to `openapi/openapi.json`. Use it with:

- **Python:** `openapi-python-client generate --path openapi/openapi.json ...`
- **TypeScript:** `npx openapi-typescript openapi/openapi.json -o sdk-js/src/generated/openapi.d.ts`

## Packages

| Package            | Role                                      |
|--------------------|-------------------------------------------|
| `agentforge`       | Local runtime: load export JSON, LangGraph |
| `agentforge-client`| Remote API: auth, CRUD, execute           |
| `@agentforge/sdk`  | TS: graph builder + generated API types  |
