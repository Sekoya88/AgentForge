# AgentForge — Developer Reference

> **TL;DR** — AgentForge is a **production-grade, self-hosted LLM agent platform**.
> Build agents visually or in code, run them on your infra, ship them as portable JSON,
> evaluate them in CI, observe them with Langfuse or LangSmith, red-team them automatically.
> Faster to deploy than LangChain, leaner than Agno, runs on your own Postgres.

---

## Table of Contents

1. [What is AgentForge?](#what-is-agentforge)
2. [Architecture overview](#architecture-overview)
3. [Core concepts](#core-concepts)
   - [Agent & Graph definition](#agent--graph-definition)
   - [Node types](#node-types)
   - [Edge conditions](#edge-conditions)
   - [Execution policy](#execution-policy)
   - [Skills](#skills)
4. [Running the platform](#running-the-platform)
5. [REST API reference](#rest-api-reference)
6. [SDK — LocalAgent, CLI](#sdk--localagent-cli)
   - [Install](#install)
   - [LocalAgent (Python)](#localagent-python)
   - [CLI commands](#cli-commands)
7. [Observability](#observability)
8. [Security & red-teaming](#security--red-teaming)
9. [Fine-tuning](#fine-tuning)
10. [Evolution log](#evolution-log)
11. [Why not LangChain / Agno?](#why-not-langchain--agno)

---

## What is AgentForge?

AgentForge is a **monorepo** containing:

| Layer | Stack | Role |
|---|---|---|
| `backend/` | FastAPI + LangGraph + Postgres + Redis | API server, orchestration, persistence |
| `frontend/` | Next.js 15 App Router + Tailwind | Visual graph builder + dashboard |
| `sdk/` | Pure Python 3.11+, zero heavy deps | Local runner + CLI for CI/CD |

It solves the **agent portability problem**: you build an agent on the platform, export it as a self-contained JSON file, run it locally with `agentforge run`, ship it in CI with `agentforge eval`, or push it to another instance with `agentforge push`. No vendor lock-in.

---

## Architecture overview

```
┌──────────────────────────────────────────────────────────────┐
│  Next.js frontend (port 3000)                                │
│  Visual builder  ·  Dashboard  ·  Campaigns  ·  Skills       │
└────────────────────────┬─────────────────────────────────────┘
                         │ REST + SSE
┌────────────────────────▼─────────────────────────────────────┐
│  FastAPI (port 8000)                                         │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌─────────────┐  │
│  │ /agents  │  │ /skills  │  │ /camps  │  │ /sandbox    │  │
│  └────┬─────┘  └──────────┘  └────┬────┘  └─────────────┘  │
│       │  Application layer         │                         │
│  ┌────▼──────────────────┐   ┌─────▼──────┐                 │
│  │   AgentService        │   │ CampaignSvc│                 │
│  └────┬──────────────────┘   └────────────┘                 │
│       │  Domain / Ports                                      │
│  ┌────▼──────────────────────────────────┐                  │
│  │  LangGraphAgentOrchestrator           │                  │
│  │  · 5 node types  · ExecutionPolicy    │                  │
│  │  · Subagent delegation  · HITL        │                  │
│  └────┬──────────────────────────────────┘                  │
│       │                                                      │
│  ┌────▼──────┐  ┌────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Postgres  │  │ Redis  │  │ Langfuse │  │  LangSmith  │  │
│  │ (agents,  │  │ (SSE   │  │  spans   │  │  runs       │  │
│  │ execs,    │  │ stream)│  └──────────┘  └─────────────┘  │
│  │ versions) │  └────────┘                                  │
│  └───────────┘                                              │
└──────────────────────────────────────────────────────────────┘

        ▲ Export / Import (JSON)
┌───────┴──────────┐
│  agentforge SDK  │  pip install agentforge-sdk
│  LocalAgent      │  run · validate · pull · push · eval
└──────────────────┘
```

**Clean Architecture** is enforced:
- `domain/` has **no imports from infrastructure** (ports are abstract interfaces)
- `application/` services wire domain + ports
- `infrastructure/` provides implementations (Postgres, Redis, LangGraph, Langfuse…)
- `api/` is thin FastAPI glue — no business logic

---

## Core concepts

### Agent & Graph definition

An **Agent** is a named, versioned graph of nodes connected by edges. It is stored as JSON in Postgres and can be exported/imported as a portable bundle.

```json
{
  "name": "Support bot",
  "description": "Triages tickets",
  "graph_definition": {
    "nodes": [
      { "id": "classify", "type": "llm",  "config": { "prompt": "Classify the intent." } },
      { "id": "escalate", "type": "tool", "config": { "tool_name": "create_ticket" } },
      { "id": "respond",  "type": "llm",  "config": { "prompt": "Draft a reply." } }
    ],
    "edges": [
      { "from": "classify", "to": "escalate", "condition": "urgent",   "condition_type": "contains" },
      { "from": "classify", "to": "respond",   "condition": ".*low.*", "condition_type": "regex" },
      { "from": "escalate", "to": "respond",   "condition_type": "always" }
    ],
    "entry_point": "classify"
  },
  "model_config": { "provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2 },
  "execution_policy": { "allowed_tools": ["create_ticket"], "max_graph_steps": 20 }
}
```

### Node types

| Type | What it does | Key config keys |
|---|---|---|
| `llm` | Calls an LLM with the accumulated messages | `prompt` (system prompt) |
| `tool` | Runs a registered skill by name | `tool_name` |
| `subagent` | Delegates to another agent by UUID | `subagent_id` |
| `conditional` | Routing only — no LLM call, dispatches on last AI message | *(no special config)* |
| `interrupt` | Pauses execution for human review (HITL) | *(none)* |

**Subagent recursion depth** is capped at 5 levels (`_MAX_SUBAGENT_DEPTH`). Circular delegation is detected and fails fast.

### Edge conditions

Four routing strategies, all backward-compatible:

| `condition_type` | Behaviour | Example `condition` |
|---|---|---|
| `"contains"` *(default)* | Case-insensitive substring match on last AI message | `"urgent"` |
| `"regex"` | Full regex search (IGNORECASE) | `".*critical.*error"` |
| `"json_path"` | Extracts JSON from last message, navigates path | `"status.code==500"` or `"flags.urgent"` |
| `"always"` | Unconditional (default/fallback edge) | *(any value or omit condition)* |

**Routing algorithm**: conditions are evaluated in declaration order; first match wins; `"always"` edges act as the fallback if no condition matches.

### Execution policy

`execution_policy` is stored per-agent and enforced at runtime by the orchestrator **before** any tool or fetch runs:

```json
{
  "allowed_tools": ["search", "send_email"],
  "denied_tools": ["shell_exec"],
  "allowed_fetch_url_prefixes": ["https://api.internal.com/"],
  "max_graph_steps": 50,
  "deny_patterns": ["password", "secret", "Bearer\\s+\\S+"],
  "require_human_approval_for": ["send_email", "delete_record"]
}
```

| Field | Type | Effect |
|---|---|---|
| `allowed_tools` | `string[] \| null` | Allowlist. `null` = unrestricted |
| `denied_tools` | `string[]` | Blocklist. Always checked first |
| `allowed_fetch_url_prefixes` | `string[] \| null` | URL scope for fetch tool. Empty list = fetch disabled |
| `max_graph_steps` | `int \| null` | LangGraph `recursion_limit` cap (1–500) |
| `deny_patterns` | `string[]` | Regex patterns on tool input text — blocked if any matches |
| `require_human_approval_for` | `string[]` | Triggers HITL interrupt before those tools execute |

### Skills

A **skill** is a named, versioned Python function stored in the registry. It is attached to an agent by UUID and resolved at execution time.

```python
# Skill source_code — must define a run(input: str) -> str function
def run(input: str) -> str:
    import httpx
    resp = httpx.get(f"https://api.myservice.com/search?q={input}")
    return resp.json()["results"][0]["title"]
```

Skills support:
- **`code`** type: Python code with a `run(input)` function
- **`instruction`** type: plain text instruction injected as context

When exported with `?include_skills=true`, each embedded skill includes a `sha256` integrity hash. The SDK verifies this hash on load and warns if tampered.

---

## Running the platform

### Prerequisites

- Docker (for Postgres + Redis)
- Python 3.12
- Node.js 20+

### Start

```bash
# 1. Infrastructure
docker compose up -d db redis
# Postgres on host :5433, Redis on host :6380

# 2. Backend
cd backend
pip install uv
uv pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
# → http://localhost:8000

# 3. Frontend
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Environment variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5433/agentforge
REDIS_URL=redis://localhost:6380/0
JWT_SECRET_KEY=change-me-min-32-chars

# LLM providers (one or more)
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...

# Observability (optional)
OBSERVABILITY_BACKEND=langfuse         # langfuse | langsmith | both | none
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=my-project

# Sentry (optional)
SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production
```

---

## REST API reference

All routes are under `/api/v1/`. Authentication: `Authorization: Bearer <JWT>`.

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register `{email, password, display_name}` |
| `POST` | `/auth/login` | Login → `{access_token, refresh_token}` |
| `POST` | `/auth/refresh` | Refresh access token |

### Agents

| Method | Path | Description |
|---|---|---|
| `GET` | `/agents` | List all agents |
| `POST` | `/agents` | Create agent |
| `GET` | `/agents/{id}` | Get agent |
| `PUT` | `/agents/{id}` | Update agent (creates version snapshot) |
| `DELETE` | `/agents/{id}` | Delete agent |
| `POST` | `/agents/import` | Import from JSON export |
| `POST` | `/agents/import-yaml` | Import from YAML export |
| `GET` | `/agents/{id}/export` | Export as portable JSON (`?include_skills=true` embeds skill source) |
| `POST` | `/agents/{id}/execute` | Execute `{input_messages, run_async}` |
| `GET` | `/agents/{id}/stream/{exec_id}` | SSE stream of execution events |
| `GET` | `/agents/{id}/executions` | List executions |
| `GET` | `/agents/{id}/executions/{exec_id}` | Get execution |
| `POST` | `/agents/{id}/executions/{exec_id}/interrupt` | Resume HITL with `{decisions}` |
| `POST` | `/agents/{id}/executions/{exec_id}/feedback` | Submit feedback `{score, comment}` |
| `GET` | `/agents/{id}/versions` | List version snapshots |
| `GET` | `/agents/{id}/versions/{n}` | Get specific version |
| `GET` | `/agents/{id}/versions/diff?from=1&to=3` | Diff two versions |
| `POST` | `/agents/{id}/rollback/{n}` | Rollback agent to version N |
| `GET` | `/agents/{id}/scorecard` | Aggregate quality scorecard |
| `GET` | `/agents/{id}/stats/versions` | Execution stats grouped by version |

### Skills

| Method | Path | Description |
|---|---|---|
| `GET` | `/skills` | List skills |
| `POST` | `/skills` | Create skill |
| `PUT` | `/skills/{id}` | Update skill |
| `DELETE` | `/skills/{id}` | Delete skill |

### Campaigns (red-teaming)

| Method | Path | Description |
|---|---|---|
| `GET` | `/campaigns` | List campaigns (`?agent_id=…`) |
| `POST` | `/campaigns` | Launch red-team campaign |
| `GET` | `/campaigns/{id}` | Get campaign report |

### Sandbox

| Method | Path | Description |
|---|---|---|
| `POST` | `/sandbox/run` | Run arbitrary code `{code, language}` |
| `GET` | `/sandbox/stream/{job_id}` | SSE stream of sandbox output |

---

## SDK — LocalAgent, CLI

The SDK is a **standalone Python package** with no dependency on the backend. It requires only `langchain-core`, `langgraph`, and one LLM provider package.

### Install

```bash
pip install agentforge-sdk
# or from the repo
pip install ./sdk
```

### LocalAgent (Python)

Run any exported agent JSON locally — no server required:

```python
import asyncio
import json
from agentforge.agent import load_agent

# Load from file or from dict
agent = load_agent("my_agent.json")

# Async invoke
result = asyncio.run(agent.ainvoke({
    "messages": [{"role": "user", "content": "Summarise this ticket: #4512"}]
}))

# Last message is the final output
print(result["messages"][-1].content)
```

**`LocalAgent` supports all 5 node types** (subagent nodes print a stub; interrupt nodes are bypassed). It uses the same conditional routing logic as the backend orchestrator, including `regex` and `json_path` conditions.

**SHA256 skill integrity** — if the export includes embedded skills with `sha256` fields, the SDK verifies each one at load time and prints a warning on mismatch:

```
Warning: skill 'send_email' sha256 mismatch — source may have been tampered with
```

### CLI commands

#### `agentforge validate`

Validate the graph structure of an export file. Exits 0 if valid, 1 on error. Use in pre-commit hooks or CI.

```bash
agentforge validate agent_export.json
# ok: graph_definition is valid
```

#### `agentforge run`

Run an agent locally with a single message. Useful for smoke-testing after `pull`.

```bash
agentforge run agent_export.json -m "Hello, what can you do?"
```

#### `agentforge pull`

Download a live agent from the platform as a portable JSON file.

```bash
export AGENTFORGE_API_URL=https://forge.mycompany.com
export AGENTFORGE_TOKEN=<jwt>

# Pull latest version
agentforge pull <agent-uuid> -o my_agent.json

# Pin to a specific version
agentforge pull <agent-uuid> --version 3 -o my_agent_v3.json
```

#### `agentforge push`

Upload a local JSON file to the platform (create or re-import).

```bash
agentforge push my_agent.json
agentforge push my_agent.json --name "My Agent v2"
# Agent pushed successfully. ID: <uuid>
```

#### `agentforge eval`

Batch-evaluate an agent against a JSONL test file. Exits 0 if pass rate ≥ 70 %, else 1.

```bash
# eval_cases.jsonl — one case per line
# {"input": "What is 2+2?", "expected": "4"}
# {"input": "Capital of France?", "expected": "Paris"}

agentforge eval agent_export.json eval_cases.jsonl
# Passed: 8/10 (80.0%)

# Write full result details
agentforge eval agent_export.json eval_cases.jsonl --output results.json
```

Pass/fail criterion: `expected.lower() in output.lower()` (substring match). Suitable for factual Q&A, slot extraction, classification labels.

#### Typical CI pipeline

```yaml
# .github/workflows/deploy.yml
- name: Pull latest agent
  run: agentforge pull ${{ vars.AGENT_ID }} -o agent.json
  env:
    AGENTFORGE_TOKEN: ${{ secrets.AGENTFORGE_TOKEN }}
    AGENTFORGE_API_URL: ${{ vars.AGENTFORGE_URL }}

- name: Validate graph
  run: agentforge validate agent.json

- name: Regression eval
  run: agentforge eval agent.json tests/eval.jsonl
```

---

## Observability

AgentForge emits typed spans for every node execution. Configure via `OBSERVABILITY_BACKEND`:

| Value | Behaviour |
|---|---|
| `none` | No tracing (default in dev) |
| `langfuse` | Sends spans to Langfuse. Each execution = one trace |
| `langsmith` | Sends runs to LangSmith. Each execution = one root run |
| `both` | Sends to both simultaneously (chain: LangSmith → Langfuse → SSE) |

**Span types emitted:**

| Event | LangGraph → Span type | Data |
|---|---|---|
| `agent_start` | `chain` or `tool` run | `node_id`, `node_type`, `input_preview` |
| `agent_end` | run end | `output_preview`, `duration_ms` |
| `tool_call` | `tool` run (instant) | `tool_name`, `args` |
| `complete` | root run end | `message_count`, `total_duration_ms` |

All observability errors are **silently swallowed** — a Langfuse outage never breaks agent execution.

**SSE stream** (`GET /agents/{id}/stream/{exec_id}`) provides real-time execution events to the frontend regardless of the observability backend setting.

---

## Security & red-teaming

### Built-in policy enforcement

The orchestrator enforces `ExecutionPolicy` on every tool call:

1. `denied_tools` check (immediate block)
2. `allowed_tools` allowlist check
3. `deny_patterns` regex check on tool input
4. `require_human_approval_for` → triggers HITL interrupt
5. Fetch URL prefix check (for `fetch` built-in)

### Red-team campaigns

Launch an automated red-team campaign against any agent from the dashboard or API:

```bash
curl -X POST /api/v1/campaigns \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "agent_id": "<uuid>",
    "test_types": [
      "prompt_injection", "jailbreak", "toxic_content",
      "sensitive_data", "harmful_content", "offensive_language",
      "overreliance", "politics", "system_prompt_override", "rbac"
    ],
    "max_prompts_per_type": 5
  }'
```

The campaign returns a `security_score` (0–100) stored on the agent. The frontend shows:
- Score trend across campaigns
- Delta vs previous campaign
- Per-category breakdown

### CI red-team baseline

The `redteam.yml` workflow runs weekly and on `workflow_dispatch`. It:
1. Runs a 10-category campaign against a mock agent
2. Fails if `security_score < 50`
3. **Persists baseline scores** across CI runs using GitHub Actions cache:
   - On `main`: saves `.redteam-score.json` with key `redteam-baseline-main`
   - On PRs: restores baseline, runs `scripts/compare_redteam_scores.py`
   - Fails if regression > 5 points (configurable via `REDTEAM_REGRESSION_THRESHOLD`)

---

## Fine-tuning

AgentForge includes a fine-tuning pipeline (via Modal):

1. **Upload training data** → `POST /api/v1/finetune` with JSONL dataset
2. **Monitor job** → `GET /api/v1/finetune/{id}`
3. **Use in agent** — set `model_config.provider = "finetuned"` + `model_config.finetune_job_id = "<job-uuid>"`
4. **Inference** routes to `MODAL_INFERENCE_URL` (deployed with `modal deploy modal_functions/inference.py`)

---

## Evolution log

| Commit | Feature |
|---|---|
| `4aec642` | HITL interrupt modal + campaign dashboard wired end-to-end |
| `d6567b3` | Rate limiting (`@limiter.limit`), CI pipeline, test infra |
| `c87c45e` | Sentry error tracking in frontend |
| `6aacaa7` | Health check, rate limiting, tool span tests |
| `6957c3d` | OSS readiness (LICENSE, SECURITY.md, issue templates) |
| `f1fe786` | `GET /agents/{id}/stats/versions` endpoint exposed |
| `561fac7` | `agentforge push` CLI command |
| `b1871a7` | Google provider fallback in generation service |
| `69beeab` | **Anthropic provider** (`claude-*` models) |
| `1d05fbb` | Migration 010 — `encrypted_anthropic_key` in `user_secrets` |
| `2909acb` | **Typed Langfuse spans** (AGENT/TOOL/GENERATION) |
| `3b51c3e` | `?include_skills=true` on export — embeds full skill source |
| `76744a1` | Fix hardcoded `gpt-5.4-mini` → `gpt-4o-mini` across codebase |
| `a6dce7a` | **ExecutionPolicy extensions**: `deny_patterns`, `require_human_approval_for` |
| `c26b17b` | **LangSmith span emitter** + `OBSERVABILITY_BACKEND=both` |
| `09ed456` | **CI baseline persistence**: `compare_redteam_scores.py`, cache on main |
| `36102f1` | **Skill SHA256**, `agentforge pull --version N`, `agentforge eval` |

---

## Why not LangChain / Agno?

| | AgentForge | LangChain | Agno |
|---|---|---|---|
| **Deployment** | Self-hosted, one `docker compose up` | Library only — you build the infra | Cloud-first SaaS |
| **Portability** | Agent = JSON file, run anywhere | Code + config, coupled to Python runtime | Proprietary bundle |
| **Visual builder** | Yes, drag-and-drop graph | No | Yes (cloud) |
| **Version control** | Built-in snapshots + rollback + diff | Manual | Manual |
| **Policy enforcement** | Allowlist/blocklist/regex/HITL at orchestrator level | Manual (decorators) | Limited |
| **Red-teaming** | Built-in campaign engine + CI integration | External (PromptFoo…) | Partial |
| **Observability** | Langfuse + LangSmith + SSE, zero-config | LangSmith opt-in | Agno cloud only |
| **Fine-tuning** | Integrated pipeline (Modal) | None | None |
| **SDK footprint** | ~3 deps, 0 server needed | Heavy dep tree | Requires Agno cloud |
| **Subagent delegation** | Native node type, depth-guarded | Manual chaining | No |
| **Eval in CI** | `agentforge eval cases.jsonl` one command | Custom scripts | No CLI |

**AgentForge is not a framework** — it is a **platform**. You don't write Python to define an agent; you describe it as data (JSON/YAML) and the platform executes it. This makes agents:
- **Portable** across environments without code changes
- **Auditable** (every version snapshot is queryable)
- **Safe by default** (policy enforcement before code runs)
- **Observable out of the box** (spans emitted without instrumentation in agent code)

---

*Branch: `research` — last updated 2026-03-28*
