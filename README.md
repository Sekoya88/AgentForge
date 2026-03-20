# AgentForge

Monorepo for **AgentForge** — build, red-team, and ship LLM agents (see `AGENTFORGE_MASTER_PROMPT.md`).

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2 async, Alembic, JWT auth, LangGraph (minimal orchestrator)
- **Frontend:** Next.js 15, React 19, Tailwind CSS 4
- **Data:** PostgreSQL 16 + pgvector (Docker), Redis (reserved for later phases)

## Quick start

1. Copy env: `cp .env.example .env` and adjust secrets.
2. Start Postgres **and Redis** (required for async execution + SSE, and sandbox streaming):

   ```bash
   docker compose up -d db redis
   ```

   Default DB is exposed on **localhost:5433** to avoid clashing with a local PostgreSQL on 5432.

3. Backend:

   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install uv && uv pip install -e ".[dev]"
   export DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5433/agentforge
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

4. Frontend:

   ```bash
   cd frontend
   npm ci
   NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
   ```

Or run everything (dev):

```bash
docker compose up --build
```

## API

- `GET /health`
- `POST /api/v1/auth/register` · `login` · `refresh` · `GET /me`
- Agents: `CRUD /api/v1/agents`, `POST .../execute` (optional `run_async: true` → `202`), `GET .../executions`, `POST .../executions/{exec_id}/interrupt` (HITL resume), `GET .../stream/{execution_id}` (SSE), `GET .../export` · `POST /api/v1/agents/import`
- Campaigns (red-team): `POST/GET/DELETE /api/v1/campaigns`, `GET .../{id}/report` — mock engine by default (`REDTEAM_MODE=mock`), optional `promptfoo` via `npx`
- Skills: `CRUD /api/v1/skills`, `POST .../{id}/validate` (stub)
- Fine-tune: `POST/GET/DELETE /api/v1/finetune`, `POST .../{id}/deploy` (stub endpoint until Modal)
- Sandbox: `POST /api/v1/sandbox/run`, `GET /api/v1/sandbox/stream/{job_id}` (async mode) — **subprocess Python only, not a security boundary**; replace with Docker/Modal for real isolation.

## Contributing

Install Git hooks once: `pip install -r requirements-dev.txt && make hooks` (installs pre-commit **and** `commit-msg` for **Conventional Commits**). See `CONTRIBUTING.md`.

## Roadmap

See `.planning/ROADMAP.md` and `.planning/STATE.md` — **05–06** (builder + conditional LangGraph + HITL interrupt/resume), **07** stub under `modal_functions/`, **08** partial (export/import, skills/finetune MVP).

## License

MIT
