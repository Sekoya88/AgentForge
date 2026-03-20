# AgentForge — Roadmap GSD

> Générée à partir de `AGENTFORGE_MASTER_PROMPT.md` via workflow **gsd-planner**. Phases, dépendances, critères de sortie alignés sur US-001..US-010 et métriques §10.

---

## Executive summary (5 bullets)

- **Plateforme verticale d’abord** : P0 = agents simples + sandbox + SSE + red-team (US-001..003) avec fondations **auth JWT**, **Postgres+pgvector**, **Redis**, **Docker Compose**, **CI** et **pyramide de tests** dès la phase 1.
- **Contrats d’intégration figés tôt** : schéma §4 (`users`, `agents`, `executions`, `campaigns`, `skills`, `finetune_jobs`, `documents`) et surface API §5 comme **référence** pour chaque phase.
- **P1** : HITL (US-004), builder multi-nœuds (US-005), QLoRA Modal (US-006), skills (US-007) — chacun sur des **ports** domaine et des **adapters** infra (LangGraph, promptfoo, Modal, sandbox).
- **P2** : comparaison de scores (US-008), import/export agent (US-009), red-team en CI (US-010) + durcissement **Langfuse + Sentry**, E2E Playwright, budgets §10 (coverage, Lighthouse).
- **8 phases max** : dépendances linéaires sur la **chaîne agent → exécution → observabilité** ; red-team après exécution stable ; fine-tune après jobs async + stockage ; P2 en dernière vague pour ne pas bloquer le MVP.

---

## Phase table (8 phases)

| # | Nom | Priorité stories | Dépend de | Sortie principale (exit criteria) |
|---|-----|------------------|-----------|-------------------------------------|
| **01** | Fondations monorepo & plateforme | — (prérequis US-*) | — | Compose up, CI verte, auth `/api/v1/auth/*`, migrations users, squelette FE/BE |
| **02** | Cœur agent (domain + API + exécution minimale) | US-001 (partiel) | 01 | CRUD agents §5.1, exécution simple, persistance `agents`/`executions` |
| **03** | Sandbox + SSE + UI exécution | US-001 (complet), US-003 | 02 | `POST /sandbox/run`, SSE §5.1/5.5, latence affichage §10 |
| **04** | Red-teaming promptfoo | US-002 | 02 | `campaigns` §5.2, score 0–100, ≥10 types de tests, durée campagne §10 |
| **05** | Builder visuel & graphe multi-agents | US-005 | 02, 03 | `graph_definition` JSON → LangGraph, ≥3 nœuds, edges conditionnels |
| **06** | Human-in-the-loop | US-004 | 02, 03, 05 | `interrupt_config`, `POST .../interrupt`, modal + reprise flux |
| **07** | Fine-tuning Unsloth QLoRA sur Modal | US-006 | 01, 02 | `finetune` §5.3, Modal `train`/deploy, métriques §10 |
| **08** | Skills marketplace, P2, prod-hardening | US-007..010 | 01–07 | Skills §5.4, comparaison scores, import/export, CI red-team, observabilité & E2E |

---

## Phase 01 — Fondations monorepo & plateforme

**Objectif** : environnement de dev reproductible, auth, schéma minimal, CI/CD et conventions Clean Architecture (domain sans infra).

**Dépendances** : aucune.

**Intégration §4** : `users` ; Alembic ; extension **pgvector** prête (même si RAG plus tard).

**Intégration §5** : `POST/GET /api/v1/auth/register|login|refresh|me`.

**Tâches (ordonnées)**

1. Monorepo `backend/`, `frontend/`, `docker-compose.yml` (services du spec §8).
2. FastAPI async, `Settings` Pydantic v2, middleware erreurs, CORS, OpenAPI.
3. SQLAlchemy 2 async + Alembic ; modèle `users` ; JWT (python-jose).
4. Next.js 15 App Router, Tailwind/shadcn, client API typé, pages login/register.
5. GitHub Actions : lint (Ruff, ESLint), tests backend (pytest), build frontend.
6. Hooks/tests : smoke `GET /health`, test auth register/login.

**Critères d’acceptation**

- `docker compose up` → API + DB + Redis + FE accessibles.
- Inscription / login → JWT utilisable sur routes protégées.
- CI passe sur branche principale.

**Risques / blockers**

- Secrets Modal/API keys : documenter `.env.example` sans secrets réels.
- Alignement versions Python 3.12 / Node pour CI.

**Cross-cutting**

- Observabilité : placeholders Sentry + structlog + `correlation_id`.
- Tests : `conftest.py`, base de tests integration DB.

---

## Phase 02 — Cœur agent (domain, persistence, exécution minimale)

**Objectif** : premier flux « créer agent → exécuter » avec graphe minimal (1× LLM + 1× tool) côté backend.

**Stories** : **US-001** (partiel — sans UI builder riche).

**Dépendances** : Phase 01.

**§4** : `agents`, `executions` ; champs `graph_definition`, `model_config`, `thread_id`, statuts.

**§5** : `POST/GET/PUT/DELETE /api/v1/agents`, `POST .../execute`, `GET .../executions`, `GET .../executions/{exec_id}`.

**Tâches**

1. Domain : entités Agent, Execution ; ports `AgentRepository`, `AgentOrchestrator`.
2. Infra : repos Postgres ; adapter LangGraph **minimal** (compilation JSON → graphe 1 LLM + 1 tool).
3. Use cases : create/update agent, start execution, get execution.
4. API Pydantic § schemas ; routes agents ; tests d’intégration endpoints.
5. Frontend minimal : liste agents, formulaire création (JSON assisté ou wizard simple), bouton exécuter.

**Critères d’acceptation**

- Agent créé avec définition conforme au contrat JSON (cf. §6.1).
- Exécution crée ligne `executions`, statuts cohérents.
- **US-001** : réponse agent obtenue (sandbox complète idéalement en phase 3).

**Risques**

- Complexité LangGraph vs. time-to-value : garder un seul chemin heureux documenté.
- Fuites de dépendances domaine → infra : revues strictes.

---

## Phase 03 — Sandbox + streaming SSE + monitoring exécution

**Objectif** : isolation d’exécution, logs temps réel, complétion US-001 et US-003.

**Stories** : **US-001** (complet), **US-003**.

**Dépendances** : Phase 02.

**§5** : `GET /api/v1/agents/{id}/stream/{exec_id}` (SSE) ; `POST /api/v1/sandbox/run`, `GET /api/v1/sandbox/stream/{id}`.

**Tâches**

1. Redis checkpointer LangGraph + canal `execution:{exec_id}` ; `sse_broadcaster`.
2. Adapter sandbox (Modal et/ou Docker fallback selon spec).
3. UI : `ExecutionLog`, connexion EventSource, affichage tool_call / erreurs.
4. Tests intégration latence **event → client mock < 200ms** (§10).

**Critères d’acceptation**

- **US-003** : événements SSE visibles avec types §6.5.
- **§10** : latence SSE < 200ms (mesurée en intégration ou staging).

**Risques**

- Backpressure SSE / timeouts proxies : documenter limites dev vs prod.
- Docker sandbox sur macOS vs Linux CI.

**Cross-cutting**

- **Langfuse** : traces des appels LLM sur le chemin d’exécution (spans minimaux).

---

## Phase 04 — Red-teaming (promptfoo)

**Objectif** : campagnes automatisées, rapport et score sécurité.

**Stories** : **US-002**.

**Dépendances** : Phase 02 ; idéalement 03 pour cible HTTP/stream.

**§4** : table `campaigns` ; mise à jour `agents.security_score`.

**§5** : §5.2 complet.

**Tâches**

1. Port `RedTeamEngine` ; adapter **promptfoo** (génération YAML, CLI, parse JSON).
2. `config_generator` depuis `graph_definition` + `model_config` + skills (logique §6.2).
3. Job async (Celery ou Modal function wrapper) pour campagnes longues.
4. UI : dashboard (score, vulns par catégorie, timeline).
5. Seuil **≥ 10 types de tests** par campagne configurée par défaut.

**Critères d’acceptation**

- **US-002** : rapport avec score 0–100 et breakdown.
- **§10** : campagne ~50 tests **< 10 min** (conditions de référence documentées).

**Risques**

- promptfoo en CI/containers : binaires, cache.
- Trop de plugins → explosion durée : presets OWASP/NIST dans `promptfoo_templates/`.

---

## Phase 05 — Builder visuel (React Flow) & multi-agents

**Objectif** : édition drag-and-drop, compilation vers LangGraph, pipelines supervisor + sous-agents.

**Stories** : **US-005**.

**Dépendances** : Phases 02, 03.

**Tâches**

1. Frontend : `AgentCanvas`, palette (LLM, tool, subagent, conditional, interrupt placeholder), panneau config.
2. Orchestrateur : mapping types nœuds §6.1 (subagent, conditional).
3. Validation Zod côté client + Pydantic côté serveur pour `graph_definition`.
4. Tests : snapshots graphe + test compilation unitaire.

**Critères d’acceptation**

- **US-005** : ≥ 3 nœuds, edges conditionnels, prévisualisation graphe.

**Risques**

- Explosion complexité UI : feature flags / nœuds progressifs.
- Compatibilité Deep Agents SDK.

---

## Phase 06 — Human-in-the-loop (interrupts)

**Objectif** : pause, décision humaine, reprise ; configuration par outil.

**Stories** : **US-004**.

**Dépendances** : Phases 02, 03, 05.

**§5** : `POST /api/v1/agents/{id}/executions/{exec_id}/interrupt`.

**Tâches**

1. Middleware `interrupt_handler` §6.4 ; nœud type `interrupt` / tools flaggés.
2. SSE événements `interrupt` §6.5.
3. UI `InterruptModal` (approve / reject / edit selon config).
4. Reprise via Command(resume=...) LangGraph ; tests intégration pause/reprise.

**Critères d’acceptation**

- **US-004** : pause visible, modal, reprise correcte du workflow.

**Risques**

- Race conditions reprise API vs UI : idempotence et états `paused`.

---

## Phase 07 — Fine-tuning QLoRA (Unsloth) sur Modal

**Objectif** : jobs GPU serverless, métriques, déploiement endpoint.

**Stories** : **US-006**.

**Dépendances** : Phase 01 (secrets Modal), Phase 02.

**§5** : §5.3.

**Tâches**

1. `modal_functions/train.py` §6.3 ; volume/paths ; retour métriques.
2. `modal_functions/inference.py` pour deploy.
3. API + use cases : création job, polling statut, annulation, deploy.
4. UI : upload dataset, suivi loss, bouton deploy.
5. Stockage datasets (S3/Modal volume — choix documenté).

**Critères d’acceptation**

- **US-006** : fine-tune + deploy **1 clic** depuis l’UI.
- **§10** : 7B, 1 epoch, 1K samples **< 30 min** (référence matérielle documentée).

**Risques**

- Coût GPU / quotas Modal.
- Builds CI lentes (images Unsloth) → cache.

---

## Phase 08 — Skills, advanced P2, hardening prod

**Objectif** : skills réutilisables, P2, automatisation CI, qualité.

**Stories** : **US-007**, **US-008**, **US-009**, **US-010**.

**Dépendances** : Phases 01–07.

**Extension contrat** : endpoints import/export agents (ex. `POST /api/v1/agents/import`, `GET .../export`) à figer à l’implémentation.

**Tâches**

1. **US-007** : CRUD skills, `skill_loader`, `POST .../validate`, sandbox + attachement agent.
2. **US-008** : historisation scores / versions ; UI comparaison.
3. **US-009** : export/import versionné `graph_definition` + `model_config`.
4. **US-010** : GitHub Actions → campagne promptfoo sur merge.
5. Langfuse dashboards, Sentry release tracking, Playwright E2E, **Lighthouse > 90** (§10), doc opérateur.

**Critères d’acceptation**

- **§10** : coverage backend **> 80%** ; Lighthouse **> 90** sur pages clés.

**Risques**

- US-010 : coût API LLM en CI — budgets et mocks.

---

## Mapping P0 / P1 / P2

| Priorité | Stories | Phases principales |
|----------|---------|---------------------|
| **P0 MVP** | US-001, US-002, US-003 | 01 → 04 (avec 02–03) |
| **P1** | US-004, US-005, US-006, US-007 | 05, 06, 07, 08 (US-007) |
| **P2** | US-008, US-009, US-010 | 08 |

---

## Artifacts GSD recommandés

| Fichier | Rôle |
|---------|------|
| `.planning/PROJECT.md` | Vision, stack, contraintes |
| `.planning/ROADMAP.md` | Ce document — phases, état |
| `.planning/STATE.md` | Décisions, blockers, phase courante |
| `.planning/phases/NN-slug/NN-CONTEXT.md` | Sortie discuss-phase |
| `.planning/phases/NN-slug/NN-RESEARCH.md` | Optionnel (Modal, promptfoo, LangGraph) |
| `.planning/phases/NN-slug/NN-01-PLAN.md` | Plans exécutables GSD |
| `.planning/phases/NN-slug/NN-01-SUMMARY.md` | Preuves, vérifs |
| `CLAUDE.md`, `README.md` | Instructions agent + run local |

---

## Références

- `AGENTFORGE_MASTER_PROMPT.md` (architecture, §4–8, user stories §7, métriques §10)
