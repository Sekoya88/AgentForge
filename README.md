# AgentForge

**Design, build, fine-tune, red-team, and deploy autonomous LLM agents — all from one platform.**

AgentForge is a full-stack workbench for developing safe LLM agents. You visually assemble agent graphs (LangGraph), attach Python skills, connect any LLM provider (or your own fine-tuned model on GPU), run automated security assessments, and iterate until the agent is hardened — then export or share it.

> **In-app walkthrough:** open **`/walkthrough`** after sign-in for scenario-based flows and deep links into the product.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Frontend User Guide](#frontend-user-guide)
3. [User Journey](#user-journey)
4. [Features](#features)
5. [API Overview](#api-overview)
6. [Developer Packages](#developer-packages)
7. [Architecture](#architecture)
8. [Project Structure](#project-structure)
9. [Development](#development)
10. [Production Deployment](#production-deployment)
11. [Tech Stack](#tech-stack)

---

## Quick Start

### Prerequisites

- **Docker** (for PostgreSQL + Redis)
- **Python 3.12+** with [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** (for frontend)

### 1. Environment

```bash
cp .env.example .env
# Required: set JWT_SECRET_KEY
# Optional: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
```

### 2. Backend virtualenv

```bash
cd backend && uv sync
```

### 3. Database & Redis

```bash
make dev-ready
# Equivalent to:
docker compose up -d db redis
cd backend && uv run alembic upgrade head
```

### 4. Start everything

Ensure **port 8000 is free** for the API (`lsof -i :8000` — another app on that port will break all frontend `fetch` calls). Then:

```bash
make quick-start          # API (port 8000) + UI (port 3000) concurrently
```

Or separately:

```bash
make backend-dev          # FastAPI with hot reload
make frontend-dev         # Next.js dev server
```

### 5. Open

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Frontend |
| http://localhost:3000/walkthrough | Guided “try these flows” (onboarding scenarios) |
| http://localhost:8000/docs | OpenAPI / Swagger |
| http://localhost:8000/health | DB + Redis health check |

### 6. Seed demo data (optional)

```bash
make seed
```

---

## Frontend User Guide

This section walks you through every page and section of the AgentForge web interface.

### Navigation

The left sidebar provides access to all sections:

| Icon | Section | What you do here |
|------|---------|-----------------|
| Grid | **Dashboard** | Overview of agents, executions, costs, and security scores |
| Bot | **Agents** | Create, manage, and run your agents |
| Code | **Skills** | Write Python skills or instruction prompts |
| Database | **Knowledge** | Upload documents for RAG retrieval |
| Brain | **Fine-tune** | Launch GPU training jobs on your data |
| Shield | **Campaigns** | Red-team security assessments |
| Terminal | **Forge** | Direct LLM chat with tools |
| Play | **Executions** | Browse all execution history |
| Globe | **Hub** | Discover and share public agents |
| Settings | **Settings** | API keys, webhooks, workspace, audit log |

---

### Dashboard (`/dashboard`)

Your mission control. Shows:

- **Stats row** — total agents, executions (24 h), avg latency, active campaigns, avg security score, skills, knowledge sources
- **Recent executions** — last 10 runs with status badge, duration, agent link
- **Onboarding checklist** — guided steps shown to new users (dismissible once all steps are complete)

**Onboarding steps shown on first use:**
1. Create your first agent
2. Add a skill or knowledge source
3. Execute your agent
4. Run a security campaign
5. Explore the Forge assistant

---

### Agents (`/agents`)

Lists all your agents with health badge, model provider, last-run time, and quick-execute button. Click any agent to open its detail page.

#### Agent Detail (`/agents/<id>`)

- **Run tab** — send a message and watch real-time execution logs via SSE; interrupt modal appears if the graph has a HITL node
- **Versions tab** — version history with diff viewer; one-click rollback
- **Schedules tab** — add/edit/delete cron schedules (e.g. `0 9 * * 1`)
- **Security tab** — latest campaign score with ScoreRing; launch new campaign
- **Budget tab** — rolling 30-day spend, set a USD limit + alert threshold
- **Share tab** — generate a shareable link (view-only or execute permission)

#### Agent Builder (`/agents/<id>/builder`)

The visual graph editor:

- **Node palette** (left) — drag any node type onto the canvas
- **Canvas** — React Flow graph; draw edges between nodes
- **Inspector** (right) — click any node to edit its properties
- **Design Mode** — click the sparkle icon to describe your agent in plain English and have the graph generated automatically
- **AI suggestions** — the builder suggests plausible edges when you add a node

**Node types:**

| Node | What it does |
|------|-------------|
| **LLM** | Calls an LLM (system prompt + provider + model) |
| **Tool** | Executes a built-in tool or attached skill |
| **ASR** | Transcribes audio via Whisper or a fine-tuned model |
| **TTS** | Synthesises speech via OpenAI TTS or ElevenLabs |
| **Conditional** | Routes execution based on edge conditions (substring match) |
| **Interrupt** | Pauses for human approval (HITL) |
| **Subagent** | Delegates to another agent |
| **memory_save** | Saves context to pgvector long-term memory |
| **memory_recall** | Retrieves relevant memories before LLM inference |

#### Creating an Agent (`/agents/new`)

1. Click **New agent**
2. Fill in name, description, initial model config
3. Optionally pick a **template** (Voice Assistant, Customer Support, Code Reviewer, …)
4. Open the **Builder** and assemble your graph
5. Save → Execute

---

### Skills (`/skills`)

Two skill types:

- **Instruction** — injected as an extra system prompt block when the agent runs
- **Code** — sandboxed Python with a `run(input: str) -> str` function

Built-in templates: summarize, translate, code review, data extract, email drafter, web search, JSON transform, text stats.

**To create:** `/skills/new` → choose type → write code or instruction → save. Skills are attached to agents on the agent detail page.

---

### Knowledge (`/knowledge`)

Upload documents for semantic (RAG) search:

- Supported formats: `.txt`, `.md`, `.csv`, `.pdf`
- Or paste raw text directly
- Or ingest a URL (fetches + chunks the page automatically)

Once ingested, documents are chunked and embedded with OpenAI embeddings into pgvector. Any agent with a **Tool** node calling `retrieve` will search your corpus.

---

### Fine-tune (`/finetune`)

GPU training powered by Modal:

1. Go to `/finetune/new`
2. Choose **modality**: text SFT, Whisper ASR, or TTS voice cloning
3. Select base model and configure hyperparams
4. Launch — watch the live loss curve and progress bar via SSE
5. Once complete, click **Deploy** to spin up an inference endpoint
6. Update your agent's model config to use `provider: "finetuned"`

---

### Campaigns (`/campaigns`)

Red-team security testing:

1. Go to an agent page → **Security tab** → **Run campaign**
2. Choose attack categories (or run all 12)
3. View results at `/campaigns/<id>`:
   - **ScoreRing** — overall security score (0–100)
   - **Vulnerability table** — grouped by severity (critical / high / medium / low)
   - **Category breakdown** — prompt injection, jailbreak, PII leakage, tool misuse, …
   - **Export** — download full JSON report

---

### Forge Assistant (`/forge`)

Direct multi-turn LLM chat — no agent setup needed:

- Switch model per message (Claude, GPT, Gemini)
- Multiple tabs open simultaneously
- Built-in tools: web search, Python REPL, HuggingFace model search, AgentForge workspace
- Type `/` for slash commands (see [Forge Commands](#forge-commands))

---

### Executions (`/executions`)

Global execution history across all agents:

- Filter by agent, status, date range
- Click any execution for full log: node-by-node trace, token counts, cost, latency
- If an execution had an interrupt, the human decision is logged
- SSE stream available during active runs

---

### Hub (`/hub`)

Discover agents shared by the community (or share your own):

- Browse public agents by category
- Click **Use this agent** to clone it into your workspace
- Share your own agents from the agent detail → **Share tab** → toggle public

---

### Settings (`/settings`)

#### API Keys (Vault)

Encrypted at rest. Keys are used per-request for your agents only.

| Key | Provider | Used for |
|-----|----------|----------|
| OpenAI API Key | [platform.openai.com](https://platform.openai.com/api-keys) | GPT, Whisper, TTS, embeddings |
| Anthropic API Key | [console.anthropic.com](https://console.anthropic.com) | Claude in Forge + agents |
| Google API Key | [aistudio.google.com](https://aistudio.google.com) | Gemini in Forge + agents |
| ElevenLabs API Key | [elevenlabs.io](https://elevenlabs.io) | Premium TTS voices |
| Tavily API Key | [tavily.com](https://tavily.com) | Web search in Forge |
| HuggingFace Token | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | HF model search |

#### Webhooks

Register outbound HTTP endpoints triggered by platform events:

| Event | When it fires |
|-------|--------------|
| `execution.completed` | Agent run finished (success or error) |
| `execution.started` | Agent run begins |
| `execution.failed` | Agent run ended with an error |
| `campaign.completed` | Red-team campaign finished |
| `schedule.fired` | Scheduled agent trigger executed |
| `agent.updated` | Agent definition changed |
| `finetune.completed` | Fine-tuning job finished |

#### Workspace

Invite team members, assign roles (admin / editor / viewer), and remove access.

#### Audit Log

Immutable record of all workspace actions (agent changes, settings edits, member invites). Append-only, fire-and-forget logging with searchable table view.

---

## User Journey

A suggested path from zero to production agent:

```
Stage 1 — Setup (5 min)
  └─ Register → add API keys in Settings → Dashboard onboarding checklist appears

Stage 2 — First agent (15 min)
  └─ /agents/new → pick "Customer Support" template (or blank)
  └─ Builder: add LLM node → set system prompt → save
  └─ Execute with a test message → confirm response

Stage 3 — Enrich (30 min)
  ├─ Add a Skill (/skills/new) → attach to agent
  ├─ Upload Knowledge (/knowledge) → add Tool node calling "retrieve"
  └─ Re-execute → confirm RAG retrieval works

Stage 4 — Harden (1 hr)
  ├─ Run red-team campaign → review score + vulnerabilities
  ├─ Patch system prompt based on findings
  └─ Re-run campaign → compare score delta

Stage 5 — Automate (30 min)
  ├─ Add cron schedule (e.g. daily digest at 09:00)
  ├─ Register a webhook for execution.completed
  └─ Set a budget limit to cap monthly spend

Stage 6 — Scale (optional)
  ├─ Fine-tune a model on your execution history
  ├─ Switch agent to finetuned provider
  ├─ Voice: add ASR + TTS nodes for audio interface
  └─ Share agent on Hub or export as Python script

Stage 7 — Operate
  ├─ Monitor dashboard: costs, latency, error rate
  ├─ Browse Executions for debugging
  └─ Review Audit Log for team changes
```

---

## Features

### Agent System

- **Visual graph builder** — drag-and-drop nodes with React Flow; color-coded by type
- **Design Mode** — describe your agent in plain English, AI generates the graph
- **AI-suggested connections** — builder proposes edges when nodes are added
- **5 LLM providers** — `mock`, `openai`, `google`/`gemini`, `anthropic`, `finetuned`
- **Built-in tools** — `echo`, `fetch`, `retrieve` (RAG), `web_search`, `python_repl`
- **Subagent delegation** — one agent can call another as a graph node
- **Conditional routing** — edge conditions with substring match on AI output
- **HITL interrupts** — pause for human approval (approve / reject / edit)
- **Agent versioning** — automatic snapshots, diff viewer, one-click rollback
- **Export / Import** — Python script, Docker archive, LangGraph JSON, or raw JSON
- **Per-agent budgets** — rolling 30-day spend vs configurable USD limit + alert threshold
- **Long-term memory** — pgvector-backed; `memory_save` / `memory_recall` nodes
- **Cron schedules** — recurring agent runs on any cron expression
- **Share links** — generate view-only or execute-permission URLs
- **Composite health score** — combines security, latency, error rate, and coverage metrics
- **Agent Hub** — public marketplace for sharing agents

### Webhooks

Outbound webhooks with HMAC-SHA256 signature verification and fire-and-forget delivery for:
`execution.completed`, `execution.started`, `execution.failed`, `campaign.completed`, `schedule.fired`, `agent.updated`, `finetune.completed`

### Voice (ASR + TTS)

- **ASR node** — Whisper or custom fine-tuned model
- **TTS node** — OpenAI TTS or ElevenLabs
- **Voice Assistant template** — one-click ASR → LLM → TTS pipeline
- **Audio endpoint** — `POST /api/v1/agents/{id}/execute/audio` (WAV/MP3 → base64 MP3 response)

### Skills

- **Instruction** — system prompt injection
- **Code** — sandboxed Python `run(str) -> str`
- **8 built-in templates** for common tasks
- **Security validation** flag for admin-reviewed skills

### Knowledge (RAG)

- Ingest `.txt`, `.md`, `.csv`, `.pdf` or raw text
- URL ingest — fetch + chunk public pages
- OpenAI embeddings in pgvector
- Semantic `retrieve` tool node

### Fine-tuning (Modal GPU)

- One-click SFT training on A10G GPUs with Unsloth + LoRA
- Whisper ASR fine-tuning and TTS voice cloning
- Live loss curve + ETA via SSE
- Model deployment → streaming inference endpoint
- Batch evaluation

### Red-team Security

- **12 attack categories** — prompt injection, jailbreak, PII leakage, tool misuse, role confusion, encoding tricks, indirect injection, system prompt leak, DoS, policy evasion, multilingual jailbreak, data exfiltration
- `mock` engine (synthetic, dev-friendly) or `promptfoo` (real testing)
- Security score with delta tracking across campaigns
- JSON export of full vulnerability report

### Forge Assistant

- Multi-turn LLM chat with Claude, GPT, or Gemini
- Multi-tab interface; per-tab model selection
- Built-in tools: web search (Tavily), Python REPL, HuggingFace search
- Slash commands (see [Forge Commands](#forge-commands))

### Observability & Hardening

- **Langfuse** — full LLM call + tool span tracing
- **Sentry** — error tracking (backend + frontend)
- **Audit log** — immutable append-only workspace action log
- **Structured JSON logging** with `X-Correlation-ID`
- **Rate limiting** — SlowAPI on all endpoints
- **PII masking** — optional redaction on execution paths
- **Health check** — `/health` verifies DB + Redis

### Workspace & Auth

- JWT auth (access + refresh tokens)
- SSO / OIDC stub (configure env vars)
- Team workspace: invite members, manage roles (admin / editor / viewer)

### Onboarding

- **Guided checklist** on dashboard — 5 steps, progress bar, dismissible
- **Empty states** on all list pages with contextual call-to-action

---

## Forge Commands

Type `/` in the Forge chat input:

| Command | Description |
|---------|-------------|
| `/help` | Show all commands and capabilities |
| `/agents` | List your agents |
| `/create agent` | Design a new agent with AI help |
| `/create skill` | Write a new skill with AI help |
| `/voice` | Guide to set up a Voice Assistant |
| `/finetune` | Guide to launching a GPU training job |
| `/redteam` | Explain red-team security campaigns |
| `/sdk` | Show Python and TypeScript SDK examples |
| `/search <query>` | Web search (Tavily key required) |
| `/python <code>` | Run Python in the sandbox REPL |

---

## API Overview

Full OpenAPI spec at `/docs`. Key endpoints:

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/health` | GET | DB + Redis health |
| `/api/v1/auth/*` | POST | Register, login, refresh, change password |
| `/api/v1/agents` | CRUD | Create, list, update, delete agents |
| `/api/v1/agents/:id/execute` | POST | Run agent (text) |
| `/api/v1/agents/:id/execute/audio` | POST | Run agent (audio blob → base64 MP3) |
| `/api/v1/agents/:id/stream/:eid` | GET (SSE) | Real-time execution stream |
| `/api/v1/agents/:id/export` | GET | Export as Python / Docker / LangGraph / JSON |
| `/api/v1/agents/:id/versions` | GET | Version history |
| `/api/v1/agents/:id/rollback/:vid` | POST | Rollback to version |
| `/api/v1/agents/:id/budget` | GET/PUT | Rolling spend vs USD limit |
| `/api/v1/agents/:id/memories` | GET/DELETE | Inspect or clear long-term memories |
| `/api/v1/agents/:id/schedules` | CRUD | Cron schedules |
| `/api/v1/agents/:id/share` | POST/GET | Share link management |
| `/api/v1/skills` | CRUD | Skills (code + instruction) |
| `/api/v1/campaigns` | POST/GET | Red-team campaigns |
| `/api/v1/campaigns/:id` | GET | Campaign report |
| `/api/v1/finetune` | CRUD | Fine-tune jobs |
| `/api/v1/finetune/trigger` | POST | Auto-trigger fine-tune from execution history |
| `/api/v1/knowledge` | POST/GET | Ingest docs, list, search |
| `/api/v1/knowledge/ingest-url` | POST | Fetch URL → chunk → embed |
| `/api/v1/knowledge/search` | GET | Semantic search (q, top_k) |
| `/api/v1/sandbox/run` | POST | Execute Python in isolated sandbox |
| `/api/v1/forge/conversations` | POST/GET | Forge multi-turn conversations |
| `/api/v1/forge/conversations/:id/execute` | POST | Send message in conversation |
| `/api/v1/forge/stream/:eid` | GET (SSE) | Forge real-time stream |
| `/api/v1/dashboard/summary` | GET | Aggregate stats |
| `/api/v1/dashboard/metrics` | GET | Daily time-series (tokens, cost, latency) |
| `/api/v1/dashboard/executions` | GET | Paginated cross-agent execution list |
| `/api/v1/webhooks` | CRUD | Outbound webhooks |
| `/api/v1/generate/*` | POST | NL → agent/skill generation |
| `/api/v1/settings/secrets` | GET/PUT | Encrypted API key vault |
| `/api/v1/workspace/members` | GET/POST | Team members |
| `/api/v1/workspace/members/:id` | PUT/DELETE | Role + removal |
| `/api/v1/audit-log` | GET | Workspace audit trail |
| `/api/v1/pii/mask` | POST | Detect + redact PII in text |
| `/api/v1/speech/deployed` | GET | Deployed speech models |
| `/api/v1/speech/voice-samples` | POST/GET | TTS voice sample management |
| `/api/v1/templates` | GET | Agent templates |
| `/api/v1/hub` | GET | Public agent hub |
| `/api/v1/sso/*` | GET | OIDC login redirect |

---

## Developer Packages

| Package | Path | Role |
|---------|------|------|
| **agentforge** (Py) | [`sdk/`](sdk/) | Local runtime: compile YAML / run exported graphs |
| **agentforge-client** (Py) | [`sdk-client/`](sdk-client/) | Full async REST client (`httpx`) — all API modules |
| **@agentforge/sdk** (TS) | [`sdk-js/`](sdk-js/) | Graph builder + OpenAPI types |
| **agentforge-mcp** | [`mcp-server/`](mcp-server/) | stdio MCP server — 31 tools covering full API |
| **OpenAPI snapshot** | [`openapi/openapi.json`](openapi/openapi.json) | `make openapi-export` to regenerate |
| **Publish CI** | [`.github/workflows/publish-sdks.yml`](.github/workflows/publish-sdks.yml) | Release → PyPI + npm (OIDC trusted publishing) |

### Python SDK (`agentforge-client`)

```python
from agentforge_client import AgentforgeClient

async with AgentforgeClient(access_token="...") as client:
    # Agents
    agents = await client.list_agents()
    result = await client.execute_agent(agent_id, [{"role": "user", "content": "Hello"}])

    # Knowledge
    await client.knowledge.ingest(text="...", title="My doc")
    hits = await client.knowledge.search("my query", top_k=5)

    # Budget
    await client.budget.set(agent_id, limit_usd=10.0, alert_threshold=0.8)
    status = await client.budget.get(agent_id)

    # Memory
    memories = await client.memory.list(agent_id)
    await client.memory.delete(agent_id, memory_id)

    # Webhooks
    await client.webhooks.create("https://...", events=["execution.completed"])

    # Schedules
    await client.schedules.create(agent_id, cron_expression="0 9 * * 1", input={})

    # Fine-tune
    job = await client.finetune.trigger(agent_id)

    # Export
    source = await client.export.python(agent_id)

    # PII
    result = await client.pii.mask("Call me at 555-1234")

    # Workspace
    await client.workspace.invite("alice@company.com", role="editor")
```

### MCP Server (`agentforge-mcp`)

31 tools exposed over stdio — use in Claude Desktop, Cursor, or any MCP host:

```json
{
  "mcpServers": {
    "agentforge": {
      "command": "uvx",
      "args": ["agentforge-mcp"],
      "env": {
        "AGENTFORGE_API_URL": "http://localhost:8000",
        "AGENTFORGE_TOKEN": "<your-jwt>"
      }
    }
  }
}
```

Available tools: `list_agents`, `get_agent`, `execute_agent`, `create_agent`, `update_agent`, `delete_agent`, `export_agent`, `list_executions`, `get_execution`, `list_all_executions`, `get_execution_metrics`, `list_skills`, `create_skill`, `search_knowledge`, `ingest_knowledge`, `ingest_knowledge_url`, `launch_campaign`, `get_campaign_report`, `forge_chat`, `create_conversation`, `get_conversation_messages`, `list_agent_memories`, `delete_agent_memory`, `list_webhooks`, `create_webhook`, `get_agent_budget`, `set_agent_budget`, `list_finetune_jobs`, `create_finetune_job`, `list_agent_schedules`, `create_agent_schedule`

---

## Architecture

```
Frontend (Next.js 15)            Backend (FastAPI)                         Infrastructure
┌──────────────────────┐        ┌──────────────────────────────────┐     ┌────────────────┐
│ Dashboard            │        │ API v1 (JWT + rate limiting)      │     │ PostgreSQL 16  │
│ Agent Builder (RF)   │◄──────►│ Core: auth, agents, skills,      │◄───►│ + pgvector     │
│ Executions / timeline│  SSE   │   knowledge, campaigns, finetune,│     │ (RAG + memory) │
│ Skill Editor         │◄──────►│   speech, sandbox, forge,        │     │ Redis 7        │
│ Fine-tune Dashboard  │        │   generation, templates, hub     │     │ (SSE + state)  │
│ Knowledge Manager    │        │ Ops: webhooks, dashboard,        │     │ Modal (GPU)    │
│ Forge Assistant      │        │   export, budget, memories,      │     │ S3 (optional)  │
│ Hub / Share          │        │   workspace, audit, PII, SSO     │     │ Langfuse       │
│ Settings / Profile   │        │                                  │     │ Sentry         │
└──────────────────────┘        │ Orchestrator (LangGraph)         │     └────────────────┘
                                │ LLM, Tool, Subagent, Conditional,│
                                │ Interrupt, ASR, TTS, memory_*    │
                                └──────────────────────────────────┘
```

| Layer | Stack |
|-------|-------|
| **API** | FastAPI, SlowAPI, JWT |
| **Domain** | Pydantic entities + ports (clean architecture) |
| **Application** | Service layer — agents, campaigns, skills, knowledge, finetune, sandbox |
| **Infrastructure** | Postgres, Redis, LangGraph, Modal, pgvector |
| **Frontend** | Next.js 15, React 19, React Flow, Recharts |

### Finding your way in the repo

| Area | Entry point |
|------|------------|
| HTTP surface | [`backend/app/api/v1/router.py`](backend/app/api/v1/router.py) |
| Graph execution | [`backend/app/infrastructure/orchestration/langgraph_orchestrator.py`](backend/app/infrastructure/orchestration/langgraph_orchestrator.py) |
| Graph JSON schema | [`docs/contracts/AFG_GRAPH.md`](docs/contracts/AFG_GRAPH.md) |
| Domain model | `backend/app/domain/` |
| DB migrations | `backend/migrations/versions/` |

---

## Project Structure

```
AgentForge/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # FastAPI routes
│   │   ├── application/      # Service layer (use-cases)
│   │   ├── domain/           # Entities, ports, value objects
│   │   └── infrastructure/   # Postgres, Redis, LangGraph, speech, red-team
│   ├── modal_functions/      # Modal GPU: train.py + inference.py
│   ├── migrations/           # Alembic migrations
│   └── tests/
│       ├── unit/             # Pure Python — domain services, diff, cost
│       └── api/              # Integration tests against real DB
├── frontend/
│   ├── src/app/              # Next.js App Router pages
│   ├── src/components/       # Shared UI components
│   └── src/lib/              # api.ts, sse.ts, onboarding.ts
├── sdk/                      # Python local runtime (agentforge)
├── sdk-client/               # Python async HTTP client (agentforge-client)
├── sdk-js/                   # TypeScript SDK (@agentforge/sdk)
├── mcp-server/               # MCP stdio server (31 tools)
├── .github/workflows/        # CI (lint, test, build) + SDK publish
├── docker-compose.yml        # Dev: Postgres + Redis + pgAdmin
├── docker-compose.prod.yml   # Production
├── Makefile                  # Dev shortcuts
└── .env.example              # Environment template
```

---

## Development

```bash
make test          # Backend pytest (unit + integration)
make e2e           # Playwright E2E tests
make tools         # pgAdmin at http://localhost:5050
make hooks         # Install pre-commit hooks
make precommit     # Ruff lint + format check
make openapi-export  # Regenerate openapi/openapi.json
```

### CI (GitHub Actions)

Every push runs:

- **Backend** — Ruff lint, pytest with real Postgres + Redis, coverage gate (≥ 80%)
- **Frontend** — ESLint, TypeScript check, Next.js build
- **E2E** — Playwright API + frontend tests
- **SDK publish** — on GitHub Release: PyPI (`agentforge-client`) + npm (`@agentforge/sdk`)

---

## Fine-tuning on GPU (Modal)

```bash
pip install modal
modal setup
cd backend
modal deploy modal_functions/inference.py
```

Set in `.env`:
```
MODAL_ENABLED=true
MODAL_INFERENCE_URL=https://<workspace>--agentforge-inference-generate.modal.run
```

Training runs on A10G GPUs with Unsloth + LoRA. Once deployed, use `provider: "finetuned"` in any agent's model config.

---

## Red-team Configuration

```bash
# .env
REDTEAM_MODE=mock        # synthetic scores (default, dev-friendly)
REDTEAM_MODE=promptfoo   # real testing via npx promptfoo eval
```

---

## Production Deployment

```bash
cp .env.prod.example .env.prod
# Edit with production secrets
docker compose -f docker-compose.prod.yml up -d
```

Includes multi-worker uvicorn, health checks, resource limits, restart policies, and dependency ordering.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), Alembic |
| Orchestration | LangGraph, LangChain |
| Frontend | Next.js 15, React 19, React Flow, Recharts |
| Database | PostgreSQL 16 + pgvector |
| Cache / SSE | Redis 7 |
| GPU Training | Modal, Unsloth, LoRA |
| Voice / Speech | OpenAI Whisper, OpenAI TTS, ElevenLabs |
| Observability | Langfuse, Sentry, structlog |
| Security Testing | promptfoo, custom mock engine |
| Auth | JWT (access + refresh), SSO/OIDC stub |
| CI/CD | GitHub Actions, Docker Compose |

---

## License

MIT
