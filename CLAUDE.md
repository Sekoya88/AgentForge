# AgentForge — agent instructions

See `AGENTFORGE_MASTER_PROMPT.md` for full spec. This repo is a **monorepo**:

- `backend/` — FastAPI, Clean Architecture (`domain` / `application` / `infrastructure` / `api`), Alembic, JWT auth, LangGraph stub orchestrator
- `frontend/` — Next.js App Router, Tailwind, calls `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)

## Rules

- **Commits**: Conventional Commits (`feat:`, `fix:`, …); hooks enforce via `pre-commit install --hook-type commit-msg` (see `CONTRIBUTING.md`).
- Domain layer must not import infrastructure.
- External systems behind ports (repositories, `AgentOrchestrator`).
- Async FastAPI + `AsyncSession`; Pydantic v2 for API. JSON field `model_config` on agents is exposed as `model_config` in JSON but named `llm_model_config` in Pydantic models (reserved name).

## Run

```bash
docker compose up -d db redis
cd backend && alembic upgrade head && uvicorn app.main:app --reload
cd frontend && npm run dev
```

DB port **5433** on host (see `docker-compose.yml`). **Redis** on host **6380** (`REDIS_URL=redis://localhost:6380/0`) — needed for `run_async` executes, SSE, and sandbox streaming.

## Phase 03 endpoints

- `POST /api/v1/agents/{id}/execute` body `{ "input_messages": [...], "run_async": true }` → `202`, then `GET .../stream/{execution_id}` (SSE) with `Authorization: Bearer …`.
- `POST /api/v1/sandbox/run` · `GET /api/v1/sandbox/stream/{job_id}`.

## Tests

```bash
cd backend && pytest
```

Integration tests need Postgres; `DATABASE_URL` defaults to `localhost:5433`.
