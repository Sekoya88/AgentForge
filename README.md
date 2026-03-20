# AgentForge

Monorepo for **AgentForge** — build, red-team, and ship LLM agents (see `AGENTFORGE_MASTER_PROMPT.md`).

Ce projet est une plateforme de création, de gestion et de déploiement d'agents IA autonomes en No-Code (via une interface visuelle Nodale) ou par le langage naturel. Il suit une **Clean Architecture (DDD)** stricte côté Backend.

## Cas d'usage concrets 🚀

Avec ce projet, tu peux (et pourras) :
1. **Créer des agents par le langage naturel :** "Crée-moi un agent de recherche qui utilise DuckDuckGo pour scraper des articles et me faire des résumés quotidiens." L'IA générera automatiquement le graphe LangGraph, les prompts, et sélectionnera les bons outils (Skills).
2. **Construire des graphes de décision visuels (React Flow) :** Relier des nœuds LLM, des nœuds Outils (Skills), et des nœuds de Routage conditionnel pour créer des Workflows complexes.
3. **Créer des Skills Python à la volée :** Générer de nouveaux outils (ex: "Crée une skill Python pour interroger l'API météo") et les attacher directement à tes agents.
4. **Human-in-the-loop (HITL) :** Ajouter des nœuds d'interruption dans le graphe. L'agent se mettra en pause, attendra ta validation (ex: avant d'envoyer un email critique), et reprendra son exécution grâce au *checkpointing* persistant sur PostgreSQL.
5. **Red-Teaming Automatisé :** Lancer des "Campagnes" d'attaques adversaires (Prompt Injection, Jailbreak) sur tes agents pour tester leur robustesse avant de les déployer.
6. **Observabilité Totale (Langfuse) :** Chaque exécution, coût, latence, et étape de raisonnement de tes agents est tracée et visible sur Langfuse.

---

## Fonctionnalités Principales

- **Backend (DDD / Clean Architecture) :**
  - **FastAPI** + **SQLAlchemy 2** (Async) + **Alembic** (Migrations).
  - Validation forte via **Pydantic**.
  - Séparation stricte des couches (`domain`, `application`, `infrastructure`, `api`).
- **Orchestration d'Agents (LangGraph) :**
  - Moteur d'exécution asynchrone avec support du Streaming (SSE).
  - Gestion de l'état et de la mémoire persistante via **AsyncPostgresSaver** (`langgraph-checkpoint-postgres`).
- **Génération IA (NLP to Graph/Code) :**
  - Services dédiés pour traduire un prompt utilisateur en définition JSON LangGraph ou en code Python exécutable (Skills).
- **Frontend (Next.js 15) :**
  - **React 19**, **Tailwind CSS 4** avec un Design System futuriste (Stitch/HTML mockups).
  - Builder visuel Drag-and-Drop interactif via **React Flow**.
- **Observabilité :**
  - Intégration native de **Langfuse** (via les Callbacks Langchain) pour le tracing des exécutions LLM.
- **Sécurité & Sandboxing :**
  - Exécution des agents dans des environnements isolés (Mock/Subprocess actuels, évolution prévue vers Docker/Modal).

---

## Quick start

1. Copy env: `cp .env.example .env` and set `JWT_SECRET_KEY` (and optional LLM/Langfuse keys).
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

4. Frontend:

   ```bash
   cd frontend
   npm ci
   NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
   ```

### Observabilité avec Langfuse

Pour activer le tracing complet de tes agents :
1. Crée un compte sur [Langfuse](https://langfuse.com/).
2. Crée un nouveau projet et récupère tes clés.
3. Ajoute-les dans ton fichier `.env` à la racine :
   ```env
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
4. Relance le Backend. Toutes les exécutions d'agents (`invoke_chat_llm`) apparaîtront désormais dans ton dashboard Langfuse (Traces, Latency, Cost, Prompts).

### Génération d'Agents par le Langage Naturel

1. Ajoute ta clé OpenAI dans `.env` :
   ```env
   OPENAI_API_KEY=sk-...
   ```
2. Va sur le Frontend : **Agents > New Agent**.
3. Dans la section "AI Generation", tape par exemple : *"A customer support agent that greets the user, uses a database lookup tool to find orders, and pauses for human approval before issuing refunds."*
4. Clique sur **Generate**. Le graphe LangGraph sera généré et configuré automatiquement !

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
- **Repo root `.env`:** set `CORS_ORIGINS` to every origin you use to open the UI, e.g. `http://localhost:3000,http://127.0.0.1:3000`.

## Real LLM (OpenAI / Gemini)

1. Set in **repo root** `.env` (never commit): `OPENAI_API_KEY` and/or `GOOGLE_API_KEY`.
2. On each agent, set `model_config`, for example:

   ```json
   { "provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2 }
   ```

   or `{ "provider": "gemini", "model": "gemini-2.5-pro" }`.

3. `provider: "mock"` keeps the previous echo behaviour (tests / offline).

## API

- `GET /health`
- `POST /api/v1/auth/register` · `login` · `refresh` · `GET /me`
- Agents: `CRUD /api/v1/agents`, `POST .../execute` (optional `run_async: true` → `202`), `GET .../executions`, `POST .../executions/{exec_id}/interrupt` (HITL resume), `GET .../stream/{execution_id}` (SSE), `GET .../export` · `POST /api/v1/agents/import`
- Generation (NLP): `POST /api/v1/generate/agent`, `POST /api/v1/generate/skill`
- Campaigns (red-team): `POST/GET/DELETE /api/v1/campaigns`, `GET .../{id}/report` — mock engine by default (`REDTEAM_MODE=mock`), optional `promptfoo` via `npx`
- Skills: `CRUD /api/v1/skills`, `POST .../{id}/validate` (stub)
- Fine-tune: `POST/GET/DELETE /api/v1/finetune`, `POST .../{id}/deploy` (stub endpoint until Modal)
- Sandbox: `POST /api/v1/sandbox/run`, `GET /api/v1/sandbox/stream/{job_id}` (async mode) — **subprocess Python only, not a security boundary**.

## License

MIT
