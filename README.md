# AgentForge

**Design, build, fine-tune, red-team, and deploy autonomous LLM agents — all from one platform.**

AgentForge is a full-stack workbench for developing safe LLM agents. You visually assemble agent graphs (LangGraph), attach Python skills, connect any LLM provider (or your own fine-tuned model on GPU), run automated security assessments, and iterate until the agent is hardened — then export it.

---

## Architecture

```
Frontend (Next.js 15)            Backend (FastAPI)                    Infrastructure
┌──────────────────────┐        ┌─────────────────────────────┐      ┌───────────────┐
│ Dashboard            │        │ API v1 (JWT + rate limiting) │      │ PostgreSQL 16 │
│ Agent Builder (RF)   │◄──────►│ ├── agents (CRUD + execute) │◄────►│ + pgvector    │
│ Skill Editor         │  SSE   │ ├── skills (code + instruct)│      │               │
│ Fine-tune Dashboard  │◄──────►│ ├── campaigns (red-team)    │      │ Redis 7       │
│ Campaign Reports     │        │ ├── finetune (Modal GPU)    │      │ (SSE + state) │
│ Knowledge Manager    │        │ ├── knowledge (RAG)         │      │               │
│ Sandbox              │        │ ├── sandbox (isolated exec) │      │ Modal (GPU)   │
│ Settings / Profile   │        │ └── generation (NL → agent) │      │ Langfuse      │
└──────────────────────┘        │                             │      │ Sentry        │
                                │ Orchestrator (LangGraph)    │      └───────────────┘
                                │ ├── 5 node types            │
                                │ ├── 5 LLM providers         │
                                │ └── HITL interrupts          │
                                └─────────────────────────────┘
```

| Layer | Stack | Role |
|-------|-------|------|
| **API** | FastAPI, SlowAPI, JWT | Auth, CRUD, SSE streaming, rate limiting |
| **Domain** | Pydantic entities + ports | Clean architecture — no infra imports |
| **Application** | Service layer | Use-cases: agents, campaigns, skills, knowledge, finetune, sandbox |
| **Infrastructure** | Postgres, Redis, LangGraph, Modal | Persistence, SSE, checkpointer, GPU training |
| **Frontend** | Next.js 15, React Flow, Recharts | Visual builder, live dashboards, streaming UI |

---

## Features

### Agent System
- **Visual graph builder** — drag-and-drop nodes (LLM, Tool, Subagent, Conditional, Interrupt) with React Flow
- **5 LLM providers** — `mock` (echo), `openai`, `google`/`gemini`, `finetuned` (your own model)
- **Built-in tools** — `echo`, `fetch` (HTTP), `retrieve` (RAG vector search)
- **Subagent delegation** — one agent can call another agent as a node
- **Conditional routing** — edge conditions with substring match on AI output
- **HITL interrupts** — pause execution for human approval (approve / reject / edit), modal UI
- **Agent versioning** — automatic snapshots, full history, one-click rollback
- **Export / Import** — JSON format for sharing agent configurations

### Skills
- **Two types**: instruction (system prompt injection) and code (sandboxed Python with `run(str) -> str`)
- **8 built-in templates** — summarize, translate, code_review, data_extract, email_drafter, web_search, json_transform, text_stats
- **Security validation** flag for admin-reviewed skills
- **Agent attachment** — skills are bound to agents by name

### Knowledge (RAG)
- **Document upload** — `.txt`, `.md`, `.csv`, bulk text ingest
- **OpenAI embeddings** — stored in pgvector for semantic search
- **Automatic retrieval** — `retrieve` tool node searches user corpus

### Fine-tuning (Modal GPU)
- **One-click training** — launch fine-tune jobs on Modal A10G GPUs
- **Unsloth + LoRA** — efficient training of Llama/Mistral models
- **Live dashboard** — real-time loss curve, gradient norm, progress bar, ETA (SSE)
- **Model deployment** — deploy inference endpoint, then use as agent LLM provider
- **Streaming inference** — token-by-token SSE from your fine-tuned model
- **Batch evaluation** — test multiple prompts against deployed model

### Red-team Security
- **Two engines**: `mock` (synthetic 12-category assessment) or `promptfoo` (real security testing via [promptfoo](https://promptfoo.dev))
- **12 attack categories** — prompt injection, jailbreak, data exfiltration, PII leakage, tool misuse, role confusion, encoding tricks, indirect injection, system prompt leak, DoS prompts, policy evasion, multilingual jailbreak
- **Security score** — per-agent score with delta tracking across campaigns
- **Campaign history** — severity-grouped vulnerabilities, ScoreRing visualization, JSON export

### Observability & Hardening
- **Langfuse tracing** — every LLM call and tool dispatch traced with spans
- **Sentry** — error tracking (backend + frontend)
- **Structured logging** — JSON access logs with `X-Correlation-ID`
- **Rate limiting** — SlowAPI on all endpoints
- **Enriched health check** — `/health` verifies DB + Redis connectivity

---

## Quick Start

### Prerequisites

- **Docker** (for PostgreSQL + Redis)
- **Python 3.12+** with [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** (for frontend + promptfoo red-team)

### 1. Environment

```bash
cp .env.example .env
# Edit .env: set JWT_SECRET_KEY (required)
# Optional: OPENAI_API_KEY, GOOGLE_API_KEY for real LLM providers
```

### 2. Database & Redis

```bash
make dev-ready
# Or manually:
docker compose up -d db redis
cd backend && alembic upgrade head
```

### 3. Backend

```bash
make backend-dev
# Or:
cd backend && uv pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend

```bash
make frontend-dev
# Or:
cd frontend && npm ci && npm run dev
```

### 5. Open

- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

### Optional: Seed Demo Data

```bash
make seed
```

---

## Usage: End-to-End Workflow

```
Register → Create Skills → Upload Knowledge → Create Agent → Build Graph
    → Attach Skills → Execute (mock/real LLM) → Fine-tune Model → Connect
    → Red-team Security Test → Iterate → Export
```

### 1. Create an account
Register at `/register`, then login. Add your API keys in `/settings` (encrypted storage).

### 2. Create skills
Go to `/skills/new`. Choose instruction type (system prompt) or code type (Python). Templates available for common tasks (web search, JSON transform, etc.).

### 3. Upload knowledge
Go to `/knowledge`. Upload documents for RAG — they're chunked and embedded with pgvector.

### 4. Create an agent
Go to `/agents/new`. Set name, description, and initial model config (`mock` for testing, `openai`/`google` for real).

### 5. Build the agent graph
Open the **Builder** (`/agents/<id>/builder`). Add nodes:
- **LLM** — system prompt + model inference
- **Tool** — calls a built-in tool or attached skill by name
- **Conditional** — routes based on edge conditions (substring match on AI output)
- **Interrupt** — pauses for human approval (HITL)
- **Subagent** — delegates to another agent

Connect nodes with edges. Set conditions on edges if using conditional routing. Choose entry point. Save.

### 6. Attach skills
On the agent detail page, select skills from the registry and save.

### 7. Execute
Type a message, check "Stream logs" for real-time SSE, hit Execute. Watch the execution flow through nodes in real time. If an interrupt node is hit, a modal pops up for approve/reject/edit.

### 8. Fine-tune a model (optional)
Go to `/finetune`. Create a training job with base model, dataset path, and hyperparams. Watch training progress live (loss curve, ETA). Once complete, deploy the inference endpoint.

### 9. Switch to fine-tuned model
Update the agent's `model_config` to `{ "provider": "finetuned", "finetune_job_id": "<uuid>" }`.

### 10. Red-team security test
On the agent page, click "Run red-team". View results in `/campaigns/<id>` with score ring, severity breakdown, and exportable JSON report.

### 11. Iterate
Modify system prompts, re-run red-team, compare score deltas. Repeat until secure.

### 12. Export
Export the agent as JSON for deployment or sharing. Import on any AgentForge instance.

---

## Fine-tuning on GPU (Modal)

AgentForge uses [Modal](https://modal.com) for serverless GPU training and inference.

### Setup

```bash
pip install modal
modal setup                    # authenticate
cd backend
modal deploy modal_functions/inference.py   # deploy inference endpoint
```

Set in `.env`:
```
MODAL_ENABLED=true
MODAL_INFERENCE_URL=https://<workspace>--agentforge-inference-generate.modal.run
```

### Training
Upload a JSONL dataset to the Modal volume, then create a job from `/finetune`. Training runs on A10G GPUs with Unsloth + LoRA.

### Inference
Once deployed, agents with `provider: "finetuned"` route LLM calls to your Modal endpoint. Supports batch evaluation and token-by-token streaming.

---

## Red-team Configuration

### Mock Mode (default)
```
REDTEAM_MODE=mock
```
Returns synthetic scores across 12 attack categories. Useful for development and UI testing.

### Promptfoo Mode (real testing)
```
REDTEAM_MODE=promptfoo
```
Requires Node.js (`npx`). Runs `promptfoo eval` with auto-generated configs against your agent. Returns real pass/fail results.

---

## Production Deployment

A production-ready Docker Compose is provided:

```bash
cp .env.prod.example .env.prod
# Edit .env.prod with production secrets
docker compose -f docker-compose.prod.yml up -d
```

Includes:
- Multi-worker uvicorn backend
- Health checks on all services
- Resource limits (CPU/memory)
- Restart policies
- Dependency ordering

---

## API Overview

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/health` | GET | DB + Redis connectivity check |
| `/api/v1/auth/*` | POST | Register, login, refresh, change password |
| `/api/v1/agents` | CRUD | Create, list, update, delete agents |
| `/api/v1/agents/:id/execute` | POST | Run agent with input messages |
| `/api/v1/agents/:id/stream/:eid` | GET (SSE) | Real-time execution stream |
| `/api/v1/agents/:id/export` | GET | Export agent as JSON |
| `/api/v1/agents/:id/import` | POST | Import agent from JSON |
| `/api/v1/agents/:id/versions` | GET | Version history |
| `/api/v1/agents/:id/rollback/:vid` | POST | Rollback to version |
| `/api/v1/skills` | CRUD | Manage skills (code + instruction) |
| `/api/v1/campaigns` | POST/GET | Launch and view red-team campaigns |
| `/api/v1/finetune` | CRUD | Fine-tune jobs (create, monitor, deploy) |
| `/api/v1/knowledge` | POST/GET | Ingest docs, upload files, search |
| `/api/v1/sandbox/run` | POST | Execute Python in isolated sandbox |
| `/api/v1/templates` | GET/POST | Agent templates (bootstrap) |
| `/api/v1/dashboard` | GET | Aggregate stats and recent executions |
| `/api/v1/generate/*` | POST | NL → agent/skill generation (requires OpenAI) |

Full OpenAPI spec available at `/docs` when the backend is running.

---

## Project Structure

```
AgentForge/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # FastAPI routes
│   │   ├── application/      # Service layer (use-cases)
│   │   ├── domain/           # Entities, ports, value objects
│   │   └── infrastructure/   # Postgres, Redis, LangGraph, red-team
│   ├── modal_functions/      # Modal GPU: train.py + inference.py
│   ├── migrations/           # Alembic database migrations
│   └── tests/                # pytest test suite
├── frontend/
│   ├── src/app/              # Next.js pages (App Router)
│   ├── src/components/       # Shared UI components
│   └── src/lib/              # API client, SSE helpers
├── docker-compose.yml        # Dev: Postgres + Redis + pgAdmin
├── docker-compose.prod.yml   # Production: all services
├── Makefile                  # Dev shortcuts
└── .env.example              # Environment template
```

---

## Development

```bash
make test          # Run backend tests
make e2e           # Run Playwright E2E tests
make tools         # pgAdmin at http://localhost:5050
make hooks         # Install pre-commit hooks
make precommit     # Run linters (Ruff, etc.)
```

### CI

GitHub Actions runs on every push:
- **Backend**: Ruff lint, pytest with Postgres + Redis
- **Frontend**: ESLint, TypeScript check, Next.js build
- **E2E**: API + frontend Playwright tests

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), Alembic |
| Orchestration | LangGraph, LangChain |
| Frontend | Next.js 15, React 19, React Flow, Recharts |
| Database | PostgreSQL 16 + pgvector |
| Cache/SSE | Redis 7 |
| GPU Training | Modal, Unsloth, LoRA |
| Observability | Langfuse, Sentry, structlog |
| Security Testing | promptfoo, custom mock engine |
| Auth | JWT (access + refresh tokens) |
| CI/CD | GitHub Actions, Docker Compose |

---

## License

MIT
