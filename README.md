# AgentForge

Monorepo for **AgentForge** — build, red-team, and ship LLM agents (see `AGENTFORGE_MASTER_PROMPT.md`).

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2 async, Alembic, JWT auth, LangGraph (minimal orchestrator)
- **Frontend:** Next.js 15, React 19, Tailwind CSS 4
- **Data:** PostgreSQL 16 + pgvector (Docker), Redis (reserved for later phases)

## Quick start

1. Copy env: `cp .env.example .env` and set `JWT_SECRET_KEY` (and optional LLM keys).
   **Important (local Docker):** keep `DATABASE_URL=...@localhost:5433/agentforge` and `REDIS_URL=redis://localhost:6380/0` as in `.env.example` — that matches `docker compose` port mappings.

2. **One command — Postgres, Redis, migrations** (Docker must be running):

   ```bash
   ./scripts/dev-up.sh
   ```

   Or: `make dev-ready` (same idea).
   Manual equivalent: `docker compose up -d db redis` then wait for health, then `cd backend && alembic upgrade head`.

   - DB: **localhost:5433** (user `forge` / password `forge`, database `agentforge`)
   - Redis: **localhost:6380**

3. Backend:

   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install uv && uv pip install -e ".[dev]"
   alembic upgrade head   # skip if dev-up.sh already ran
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Alembic reads the **repo root** `.env` automatically (`migrations/env.py`). No need to `export DATABASE_URL` if `.env` is correct.

4. Frontend:

   ```bash
   cd frontend
   npm ci
   NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
   ```

5. (Optional) E2E UI smoke (`frontend/`):

   ```bash
   cd frontend
   npx playwright install chromium   # once
   npm run test:e2e                  # starts Next on port 3010 by default
   ```

   For authenticated flows, set `E2E_EMAIL` and `E2E_PASSWORD` to a real account.

### Frontend: `ChunkLoadError` sur une route (ex. `/agents/new`)

Souvent après un **redémarrage du dev server**, un **changement de port** (3000 → 3002), ou un cache `.next` incohérent. Ferme l’onglet, puis :

```bash
cd frontend
rm -rf .next
npm run dev
```

Ou en une commande : `npm run dev:clean`. Recharge la page en **hard refresh** (Cmd+Shift+R).

### Auth & CORS (local dev)

- **401 on `/api/v1/*`:** normal until you authenticate. Use **Register** (`/register`) then **Login** (`/login`); the app stores JWTs in `localStorage` and sends `Authorization: Bearer …`.
- **Repo root `.env`:** set `CORS_ORIGINS` to every origin you use to open the UI, e.g. `http://localhost:3000,http://127.0.0.1:3000` (localhost and 127.0.0.1 are different origins).
- **OPTIONS → 400 “Disallowed CORS origin”:** Next.js often runs on **:3001** if :3000 is busy; fixed origins only allow listed ports. The API defaults to **`CORS_ORIGIN_REGEX`** matching `http(s)://localhost` and `127.0.0.1` **with any port**. Set `CORS_ORIGIN_REGEX=` empty in production if you want strict origin-only mode.
- **OPTIONS → 400 “private-network”:** Chrome may send `Access-Control-Request-Private-Network` on preflight. **`CORS_ALLOW_PRIVATE_NETWORK=true`** is the default (see `.env.example`). Restart uvicorn after changing env.

Or run everything (dev):

```bash
docker compose up --build
```

## Real LLM (OpenAI / Gemini)

1. Set in **repo root** `.env` (never commit): `OPENAI_API_KEY` and/or `GOOGLE_API_KEY`.
2. On each agent, set `model_config`, for example:

   ```json
   { "provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2 }
   ```

   or `{ "provider": "gemini", "model": "gemini-2.5-pro" }` (backend default when `model` is omitted).

3. `provider: "mock"` keeps the previous echo behaviour (tests / offline).

Graph nodes of type `llm` use the agent’s `model_config`; optional per-node overrides in `config`: `model`, `temperature`.

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
