# AgentForge

Monorepo **AgentForge** — platform to design, execute, **red-team**, version, and iterate on autonomous agents (LangGraph, Python skills, RAG). Full spec: `AGENTFORGE_MASTER_PROMPT.md`.

> **Manual testing scenarios** → see [`explain.md`](explain.md).

## Architecture overview

| Layer | Stack | Role |
|-------|-------|------|
| **API** | FastAPI `/api/v1/*` | Auth JWT, CRUD agents/skills/campaigns/finetune, knowledge, sandbox, templates, dashboard, settings, generation |
| **Domain** | Entities + ports | No infra imports; orchestration via `AgentOrchestrator` |
| **Application** | Services | Use-cases: agents, executions, campaigns, skills, knowledge (RAG), sandbox |
| **Infrastructure** | Postgres, Redis, LangGraph, subprocess/Docker | Persistence, SSE/async, Postgres checkpointer (interrupts), skills/tools |
| **Frontend** | Next.js App Router | Dashboard, Agents, Builder, Skills, Knowledge, Campaigns, Sandbox, Executions, Settings, Profile |

## What works today

- **LangGraph orchestration** — graph with nodes `llm`, `tool`, `conditional`, `interrupt`, `subagent`; providers: mock, OpenAI, Gemini
- **Built-in tools** — `echo`, `fetch`, `retrieve` (RAG on user corpus)
- **Skills registry** — Python code with `run(str) -> str`, static validation, agent attachment; `tool_name` = skill `name`
- **Knowledge (RAG)** — text ingest + file upload (.txt, .md, .csv), OpenAI embeddings, vector search via pgvector
- **Red-team campaigns** — mock engine (synthetic scores) or `promptfoo` if Node available
- **Agent templates** — 6 built-in templates to bootstrap agents (Q&A, RAG, tool-use, etc.)
- **Agent versioning** — automatic snapshots on every update, version history, rollback
- **Agent export/import** — JSON export + import for sharing agent configs
- **Docker sandbox** — isolated Python execution (optional, `SANDBOX_MODE=docker`)
- **Dashboard** — aggregate stats, recent executions
- **Execution history** — paginated list of all agent runs
- **Settings** — read-only system config (integrations, runtime, infra)
- **Profile** — view user info, change password
- **Observability** — structured logs + `X-Correlation-ID`, Langfuse callbacks, Sentry opt-in
- **Streaming** — SSE via Redis for async executions
- **NL generation** — `POST /api/v1/generate/agent|skill` (OpenAI required)

**Partial / demo:** fine-tuning (DB schema + jobs, no GPU training — Modal stub).

## Quick start

1. `cp .env.example .env` — `JWT_SECRET_KEY` required; for RAG + NL generation: `OPENAI_API_KEY`.
2. **Postgres + Redis** (host ports **5433** / **6380** from `docker-compose`):
   ```bash
   docker compose up -d db redis
   cd backend && alembic upgrade head
   ```
3. **Seed demo data** (optional):
   ```bash
   make seed
   ```
4. **Backend**:
   ```bash
   cd backend && uv pip install -e ".[dev]" && uvicorn app.main:app --reload --port 8000
   ```
5. **Frontend**:
   ```bash
   cd frontend && npm ci && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
   ```

### Extra tools

```bash
make tools     # pgAdmin at http://localhost:5050
make test      # backend pytest
make e2e       # frontend Playwright E2E
```

## API (overview)

`GET /health` · `POST /api/v1/auth/register|login|refresh|change-password` · `GET /api/v1/auth/me`

**Agents**: CRUD, `execute`, `executions`, `interrupt`, `stream` (SSE), `export`/`import`, `versions`, `rollback`

**Templates**: `GET /templates`, `GET /templates/{slug}`, `POST /templates/{slug}/create`

**Knowledge**: `GET /sources`, `POST /ingest`, `POST /upload` (multipart), `DELETE /sources/{title}`

**Dashboard**: `GET /dashboard`, `GET /dashboard/executions`

**Skills**, **Campaigns**, **Finetune**, **Sandbox**, **Settings**, **Generation** — see OpenAPI `/docs` once running.

## CI

GitHub Actions: backend (Ruff, pytest, Postgres, Redis, `REDTEAM_MODE=mock`), frontend (lint, build), E2E (API + `next start` + Playwright).

## Docs

- [`explain.md`](explain.md) — manual validation scenarios (real user flows)
- `AGENTFORGE_MASTER_PROMPT.md` — long-term vision, data schema, user stories
- [`backend/README.md`](backend/README.md), [`frontend/README.md`](frontend/README.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — hooks, E2E, commit conventions

## License

MIT
