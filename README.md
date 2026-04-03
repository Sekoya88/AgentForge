# AgentForge

**Design, build, fine-tune, red-team, and deploy autonomous LLM agents — all from one platform.**

AgentForge is a full-stack workbench for developing safe LLM agents. You visually assemble agent graphs (LangGraph), attach Python skills, connect any LLM provider (or your own fine-tuned model on GPU), run automated security assessments, and iterate until the agent is hardened — then export it.

---

## Developer packages

| Package | Path | Role |
|---------|------|------|
| **agentforge** (Py) | [`sdk/`](sdk/) | Local runtime: validate / compile YAML / run export JSON |
| **agentforge-client** (Py) | [`sdk-client/`](sdk-client/) | Async REST client (`httpx`) |
| **@agentforge/sdk** (TS) | [`sdk-js/`](sdk-js/) | Graph builder + OpenAPI types (`npm run gen:api`) |
| **agentforge-mcp** | [`mcp-server/`](mcp-server/) | stdio MCP → API (`list_agents`, `execute_agent`) |
| **OpenAPI snapshot** | [`openapi/openapi.json`](openapi/openapi.json) | Regenerate: `make openapi-export` |

Graph contract: [`docs/contracts/AFG_GRAPH.md`](docs/contracts/AFG_GRAPH.md).

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
│ Forge Assistant      │        │ ├── sandbox (isolated exec) │      │ Modal (GPU)   │
│ Sandbox              │        │ ├── forge (multi-turn LLM)  │      │ Langfuse      │
│ Settings / Profile   │        │ └── generation (NL → agent) │      │ Sentry        │
└──────────────────────┘        │                             │      └───────────────┘
                                │ Orchestrator (LangGraph)    │
                                │ ├── 7 node types            │
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
- **Visual graph builder** — drag-and-drop nodes (LLM, Tool, Subagent, ASR, TTS, Conditional, Interrupt) with React Flow
- **5 LLM providers** — `mock` (echo), `openai`, `google`/`gemini`, `anthropic`, `finetuned` (your own model)
- **Built-in tools** — `echo`, `fetch` (HTTP), `retrieve` (RAG vector search), `web_search`, `python_repl`
- **Subagent delegation** — one agent can call another agent as a node
- **Conditional routing** — edge conditions with substring match on AI output
- **HITL interrupts** — pause execution for human approval (approve / reject / edit), modal UI
- **Agent versioning** — automatic snapshots, full history, one-click rollback
- **Export / Import** — JSON format for sharing agent configurations

### Voice (ASR + TTS)
- **ASR node** — transcribes audio via OpenAI Whisper or a custom fine-tuned model
- **TTS node** — converts AI responses to audio via OpenAI TTS or ElevenLabs
- **Voice Assistant template** — ready-made ASR → LLM → TTS pipeline, one click from `/agents/new`
- **Audio execution endpoint** — `POST /api/v1/agents/{id}/execute/audio` accepts WAV/MP3 blobs
- **Speech fine-tuning** — collect transcriptions and voice samples, then fine-tune Whisper/TTS on GPU

### Forge Assistant
- **Multi-turn LLM chat** — direct access to Claude, GPT, or Gemini without building an agent
- **Built-in tools** — web search (Tavily), Python REPL, AgentForge workspace read/write, HuggingFace model search
- **Multi-tab interface** — multiple conversations open simultaneously with per-tab model selection
- **Slash commands** — type `/` in the chat to see available commands (see [Forge Commands](#forge-assistant-commands))

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

## API Keys Reference

Configure your keys in **Settings → User API Keys (Vault)**. Each key is encrypted at rest and only used for your agents/requests.

| Key | Where to get it | Used for |
|-----|----------------|---------|
| **OpenAI API Key** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | GPT chat, Whisper ASR, OpenAI TTS, embeddings (RAG), NL→agent generation |
| **Anthropic API Key** | [console.anthropic.com](https://console.anthropic.com) | Claude chat in Forge, Claude LLM nodes in agents |
| **Google API Key** | [aistudio.google.com](https://aistudio.google.com) | Gemini chat in Forge, Gemini LLM nodes in agents |
| **ElevenLabs API Key** | [elevenlabs.io](https://elevenlabs.io) | Premium TTS voices in Voice Assistant agents |
| **Tavily API Key** | [tavily.com](https://tavily.com) | Web search tool in Forge Assistant |
| **HuggingFace Token** | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | HF model/dataset search, private model access |

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
Go to `/agents/new`. Set name, description, and initial model config (`mock` for testing, `openai`/`google`/`anthropic` for real).

### 5. Build the agent graph
Open the **Builder** (`/agents/<id>/builder`). Add nodes:
- **LLM** — system prompt + model inference
- **Tool** — calls a built-in tool or attached skill by name
- **ASR** — transcribes audio input (Whisper or fine-tuned model)
- **TTS** — converts text to speech (OpenAI TTS or ElevenLabs)
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

## Voice Assistant

The Voice Assistant is a built-in template that chains ASR → LLM → TTS in a single agent graph. It supports real microphone input (via the audio execution endpoint) and plays back synthesized audio responses.

### Required API keys

| Feature | Key required |
|---------|-------------|
| Speech-to-text (Whisper) | **OpenAI API Key** |
| AI response generation | **OpenAI API Key** (or Anthropic / Google) |
| Text-to-speech (OpenAI) | **OpenAI API Key** |
| Text-to-speech (ElevenLabs) | **ElevenLabs API Key** |

### Setup — step by step

**Step 1 — Add your OpenAI key in Settings**

Go to `/settings` → **User API Keys (Vault)** → paste your `sk-...` key in **OpenAI API Key** → click **Save keys**.

This single key enables Whisper ASR + GPT chat + OpenAI TTS simultaneously.

**Step 2 — (Optional) Add your ElevenLabs key**

If you want premium voices instead of the default OpenAI "nova" voice, also paste your ElevenLabs key (`xi_...`) in the **ElevenLabs API Key** field.

**Step 3 — Create the Voice Assistant agent**

Go to `/agents/new` → click **Browse templates** → select **Voice Assistant**. This instantiates a pre-built graph with three nodes:

```
[ASR: openai_whisper] → [LLM: GPT] → [TTS: openai_tts / elevenlabs]
```

**Step 4 — Test with text first**

In the agent console, send a text message. The ASR node will skip (no audio input), the LLM node will respond, and the TTS node will return a base64-encoded audio blob in the response. Confirm it works before sending real audio.

**Step 5 — Send audio via the API**

To send actual voice input, POST audio to the dedicated endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/execute/audio \
  -H "Authorization: Bearer <your_jwt>" \
  -F "file=@recording.wav"
```

The response includes `audio_b64` (base64 MP3) that you can play back in any audio player.

**Step 6 — Switch to ElevenLabs TTS (optional)**

In the Builder, click the **TTS (speak)** node → change `provider` from `openai_tts` to `elevenlabs_tts`. Make sure your ElevenLabs key is saved in Settings. You can also set a specific `voice_id` from your ElevenLabs account.

### Customise the graph

You can modify the Voice Assistant template for your use case:

- Change the LLM node's system prompt to make the assistant domain-specific
- Add a **Tool** node after ASR (e.g. web search, retrieval) before the LLM
- Chain multiple TTS providers (OpenAI for fast responses, ElevenLabs for quality)
- Add a **Conditional** node to route long queries to a more powerful model

---

## Forge Assistant Commands

The Forge Assistant is a direct multi-turn LLM chat (no agent required). Type `/` in the chat input to see available commands:

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands and Forge capabilities |
| `/agents` | List your agents and their status |
| `/create agent` | Ask Forge to help you design a new agent |
| `/create skill` | Ask Forge to help you write a new skill |
| `/voice` | Step-by-step guide to set up your first Voice Assistant agent |
| `/finetune` | Guide to launching a fine-tuning job on GPU |
| `/redteam` | Explain how to run a red-team security campaign |
| `/sdk` | Show examples for using the Python and TypeScript SDKs |
| `/search <query>` | Search the web (requires Tavily API key) |
| `/python <code>` | Run Python code in the sandbox REPL |

**Note**: Commands are interpreted by the LLM — there is no strict parsing. Write naturally after the command for context (e.g. `/create agent that summarizes emails`).

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
| `/api/v1/agents/:id/execute` | POST | Run agent with text message |
| `/api/v1/agents/:id/execute/audio` | POST | Run agent with audio blob (WAV/MP3) → ASR → LLM → TTS |
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
| `/api/v1/speech/deployed` | GET | List deployed speech models (ASR + TTS) |
| `/api/v1/speech/voice-samples` | POST/GET | Upload voice samples for TTS fine-tuning |
| `/api/v1/templates` | GET/POST | Agent templates (bootstrap) |
| `/api/v1/forge/conversations` | POST/GET | Forge multi-turn conversations |
| `/api/v1/forge/conversations/:id/execute` | POST | Send message in Forge conversation |
| `/api/v1/forge/stream/:eid` | GET (SSE) | Real-time Forge stream |
| `/api/v1/dashboard` | GET | Aggregate stats and recent executions |
| `/api/v1/generate/*` | POST | NL → agent/skill generation (requires OpenAI) |
| `/api/v1/settings/secrets` | GET/PUT | User API keys (encrypted vault) |

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
│   │   └── infrastructure/   # Postgres, Redis, LangGraph, red-team, speech
│   ├── modal_functions/      # Modal GPU: train.py + inference.py
│   ├── migrations/           # Alembic database migrations
│   └── tests/                # pytest test suite
├── frontend/
│   ├── src/app/              # Next.js pages (App Router)
│   ├── src/components/       # Shared UI components
│   └── src/lib/              # API client, SSE helpers
├── sdk/                      # Python SDK (agentforge)
├── sdk-client/               # Python async client (agentforge-client)
├── sdk-js/                   # TypeScript SDK (@agentforge/sdk)
├── mcp-server/               # MCP stdio server
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

## Roadmap — Upcoming improvements

### Short term
- **Voice button in Forge chat** — microphone recording directly in the Forge assistant UI (browser Web Audio API → base64 → agent audio endpoint)
- **Audio playback in agent console** — inline `<audio>` player when a TTS response is returned
- **Slash command backend routing** — implement `/walkthrough voice`, `/walkthrough finetune`, etc. as backend-handled Forge commands
- **Vision nodes** — image input support in agent graphs (multi-modal LLM calls)

### Medium term
- **Streaming fine-tuned inference** — token-by-token SSE from self-hosted models (llama.cpp / vLLM)
- **Agent marketplace** — browse, clone, and rate community agent templates
- **Scheduled executions** — cron-based agent runs with result notifications
- **Webhook triggers** — execute agents on external events (GitHub, Slack, email)

### Long term
- **Multi-agent orchestration** — visual editor for agent-to-agent coordination patterns
- **Dataset builder** — label and curate training data from agent execution history
- **Custom evaluators** — plug-in LLM judges for automated quality scoring

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
| Voice/Speech | OpenAI Whisper (ASR), OpenAI TTS, ElevenLabs TTS |
| Observability | Langfuse, Sentry, structlog |
| Security Testing | promptfoo, custom mock engine |
| Auth | JWT (access + refresh tokens) |
| CI/CD | GitHub Actions, Docker Compose |

---

## License

MIT
