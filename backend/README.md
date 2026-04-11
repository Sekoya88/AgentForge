# AgentForge — Backend

Async **FastAPI** API, **Clean Architecture**: `domain` → `application` → `infrastructure` → `api`. Persistence via **SQLAlchemy 2 async** + **Alembic**; orchestration via **LangGraph**; event streaming via **Redis** (SSE, async jobs).

## Prerequisites

- Python **3.12+**
- Postgres (**pgvector** extension for `knowledge_chunks`) + Redis (recommended for async/SSE)
- **`.env`** at monorepo root (or `backend/.env`) — see `../.env.example`

## Install & run

```bash
cd backend
uv pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Key env vars: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `OPENAI_API_KEY` (LLM + embeddings), `GOOGLE_API_KEY` (Gemini), `LANGFUSE_*`, `SENTRY_DSN`, `REDTEAM_MODE` (`mock`|`promptfoo`), `SANDBOX_MODE` (`subprocess`|`docker`), `DISABLE_PGVECTOR_MEMORY` (`true`|`false`). Sandbox prod notes: `../docs/runbooks/sandbox-production.md`.

## Structure (`app/`)

| Directory | Contents |
|-----------|----------|
| `domain/` | Entities, value objects, **ports** (repos, `AgentOrchestrator`, `RedTeamEngine`, …) |
| `application/services/` | Use-cases: `agent_service`, `skill_service`, `campaign_service`, `knowledge_service`, `auth_service`, … |
| `infrastructure/` | Adapters: Postgres, Redis, `langgraph_orchestrator`, red-team (mock/promptfoo), sandbox (subprocess/Docker) |
| `api/v1/` | Routers: `agents`, `auth`, `skills`, `campaigns`, `knowledge`, `finetune`, `sandbox`, `generation`, `templates`, `dashboard`, `settings` |
| `config.py` | `Settings` Pydantic |
| `dependencies.py` | FastAPI DI (session, repos, services) |
| `main.py` | App, CORS, middlewares (correlation, access log), Sentry opt-in |

## API endpoints

### Auth
- `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`
- `POST /auth/change-password` — requires current + new password

### Agents
- CRUD: `GET /agents`, `POST /agents`, `GET /agents/{id}`, `PUT /agents/{id}`, `DELETE /agents/{id}`
- Execute: `POST /agents/{id}/execute` (sync or `run_async: true`)
- Stream: `GET /agents/{id}/stream/{execution_id}` (SSE)
- Versions: `GET /agents/{id}/versions`, `GET /agents/{id}/versions/{n}`
- Rollback: `POST /agents/{id}/rollback/{n}`
- Export/Import: `GET /agents/{id}/export`, `POST /agents/import`

### Templates
- `GET /templates`, `GET /templates/{slug}`, `POST /templates/{slug}/create`

### Knowledge
- `GET /knowledge/sources`, `POST /knowledge/ingest`, `POST /knowledge/upload` (multipart), `DELETE /knowledge/sources/{title}`

### Dashboard
- `GET /dashboard` (aggregate stats), `GET /dashboard/executions` (paginated)

### Settings
- `GET /settings` (read-only system config)

### Others
Skills, Campaigns, Finetune, Sandbox, Generation — see OpenAPI `/docs`.

## Migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

Notable revisions: agents/executions/campaigns, skills/finetune, **004** knowledge_chunks (vectors), **005** agent_versions.

### Docker image boot

The default container command (`scripts/docker_entrypoint.sh`) runs `python -m alembic upgrade head` on every start, then starts uvicorn. Re-applying migrations is idempotent. For very large data backfills, run them as a one-off job before rollout so container startup stays fast.

Production can pass extra uvicorn flags via `UVICORN_EXTRA_ARGS` (see `docker-compose.prod.yml`).

## Tests

```bash
pytest
```

Integration tests need Postgres (`localhost:5433` default). Redis optional for some flows.

## OpenAPI

Running API: **http://localhost:8000/docs**

## Links

- Monorepo README: `../README.md`
- Contributor guide / E2E: `../CONTRIBUTING.md`
