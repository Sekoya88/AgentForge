# AgentForge — Backend

API **FastAPI** async, **Clean Architecture** : `domain` → `application` → `infrastructure` → `api`. Persistance **SQLAlchemy 2 async** + **Alembic** ; orchestration **LangGraph** ; files d’événements **Redis** (SSE, jobs async).

## Prérequis

- Python **3.12+**
- Postgres (**pgvector** pour `knowledge_chunks`) + Redis (recommandé pour exécutions async / SSE)
- Fichier **`.env` à la racine du monorepo** (ou `backend/.env`) — voir `../.env.example`

## Installation & run

```bash
cd backend
uv pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Variables typiques (rappel) : `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `OPENAI_API_KEY` (LLM + embeddings knowledge), `GOOGLE_API_KEY` (Gemini), `LANGFUSE_*`, `SENTRY_DSN`, `REDTEAM_MODE` (`mock` | `promptfoo`).

## Structure (`app/`)

| Dossier | Contenu |
|---------|---------|
| `domain/` | Entités, value objects, **ports** (repos, `AgentOrchestrator`, `RedTeamEngine`, …) |
| `application/services/` | Cas d’usage : `agent_service`, `skill_service`, `campaign_service`, `knowledge_service`, … |
| `infrastructure/` | Adapters : Postgres, Redis, `langgraph_orchestrator`, red-team (mock / promptfoo), sandbox subprocess |
| `api/v1/` | Routeurs : `agents`, `auth`, `skills`, `campaigns`, `knowledge`, `finetune`, `sandbox`, `generation` |
| `config.py` | `Settings` Pydantic |
| `dependencies.py` | Injection FastAPI (session, repos, services) |
| `main.py` | App, CORS, middlewares (correlation, access log), Sentry opt-in |

## Migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"   # si tu ajoutes des modèles ORM
```

Révisions notables : schéma agents/executions/campaigns, skills/finetune, **004** `knowledge_chunks` (vecteurs).

## Tests

```bash
pytest
```

Les tests d’intégration attendent Postgres (ex. `localhost:5433` selon ton `.env`). Redis optionnel pour une partie des flux.

## OpenAPI

Avec l’API lancée : **http://localhost:8000/docs**

## Liens

- README monorepo : `../README.md`
- Guide contributeur / E2E : `../CONTRIBUTING.md`
