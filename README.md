# AgentForge

Monorepo **AgentForge** — plateforme pour concevoir, exécuter, **red-team** et itérer sur des agents (LangGraph, skills Python, RAG). Spécification longue : `AGENTFORGE_MASTER_PROMPT.md`.

> **Tester l’app comme un humain (parcours pertinents)** → voir [`explain.md`](explain.md).

## En bref (état du code)

| Couche | Stack | Rôle |
|--------|--------|------|
| **API** | FastAPI `/api/v1/*` | Auth JWT, CRUD agents/skills/campaigns/finetune, knowledge, sandbox, génération NL |
| **Domaine** | Entités + ports | Pas d’import infra ; orchestration via `AgentOrchestrator` |
| **Application** | Services | Cas d’usage : agents, exécutions, campagnes, skills, knowledge (RAG), sandbox |
| **Infra** | Postgres, Redis, LangGraph, subprocess | Persistance, SSE/async, checkpointer Postgres (interrupts), skills/outils |
| **Frontend** | Next.js App Router | Outils : Agents, Builder, Skills, **Knowledge**, Campaigns, Sandbox, Finetune (labs) |

**Ce qui est “réel” aujourd’hui :** graphe LangGraph (LLM mock/OpenAI/Gemini), tools builtin `echo` / `fetch` / **`retrieve`** (RAG utilisateur), skills registry + exécution subprocess, campagnes red-team (**mock** par défaut ou **promptfoo** si configuré), streaming SSE si Redis.

**Ce qui est encore partiel / démo :** fine-tuning (jobs en base, **pas d’entraînement GPU** — voir bannière Labs UI), sandbox = Python subprocess (pas isolation type Docker/Modal).

## Démarrage rapide

1. `cp .env.example .env` — `JWT_SECRET_KEY` obligatoire ; pour RAG + génération NL : `OPENAI_API_KEY`.
2. **Postgres + Redis** (ports host **5433** / **6380** avec le `docker-compose` du repo) :
   ```bash
   ./scripts/dev-up.sh   # ou: docker compose up -d db redis && cd backend && alembic upgrade head
   ```
3. **Backend** : `cd backend && uv pip install -e ".[dev]" && alembic upgrade head && uvicorn app.main:app --reload --port 8000`
4. **Frontend** : `cd frontend && npm ci && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`

Détails : [`backend/README.md`](backend/README.md), [`frontend/README.md`](frontend/README.md), [`CONTRIBUTING.md`](CONTRIBUTING.md) (hooks, E2E Playwright).

## Fonctionnalités principales (produit)

- **Agents** : CRUD, `graph_definition` JSON (nœuds `llm`, `tool`, `conditional`, `interrupt`, `subagent`), exécution sync ou async + SSE.
- **Builder** (React Flow) : édition visuelle + persistance.
- **Skills** : code Python avec `run(str) -> str`, validation statique, attachement agent ; `tool_name` = `name` du skill.
- **Knowledge (RAG)** : indexation texte (embeddings OpenAI), recherche via tool **`retrieve`** sur le corpus de l’utilisateur connecté.
- **Campagnes** : score / rapport ; `REDTEAM_MODE=mock` (synthétique) ou `promptfoo` si Node disponible.
- **Génération** : `POST /api/v1/generate/agent|skill` (OpenAI requis).
- **Observabilité** : logs structurés + `X-Correlation-ID` ; Langfuse (callbacks LLM) ; **Sentry** opt-in (`SENTRY_DSN`).

## Documentation complémentaire

- [`explain.md`](explain.md) — comment **valider manuellement** le front (scénarios utiles, pas du smoke vide).
- `AGENTFORGE_MASTER_PROMPT.md` — vision long terme, schéma données, user stories.
- `.planning/ROADMAP.md` / `STATE.md` — phases GSD (fichiers locaux / planning).

## API (aperçu)

`GET /health` · `POST /api/v1/auth/register|login|refresh` · `GET /api/v1/auth/me`
**Agents** : CRUD, `execute`, `executions`, `interrupt`, `stream` (SSE), `export` / `import`
**Knowledge** : `GET /knowledge/sources`, `POST /knowledge/ingest`, `DELETE /knowledge/sources/{title}`
**Skills**, **Campaigns**, **Finetune**, **Sandbox**, **Generation** — voir OpenAPI `/docs` une fois l’API lancée.

## CI

GitHub Actions : backend (Ruff, pytest, Postgres, Redis, `REDTEAM_MODE=mock`), frontend (lint, build), E2E (API + `next start` + Playwright).

## License

MIT
