# AgentForge — état GSD

## Phase courante

**07 — Fine-tuning Modal** : schéma + API `finetune_jobs` prête ; `modal_functions/` stub + README ; branchement GPU à faire.

## Fait

- **01–04** : Monorepo, auth, agents, sandbox, SSE, campaigns red-team.
- **05** : Validation Pydantic `graph_definition` ; LangGraph dynamique (edges conditionnelles par substring sur dernier message AI) ; types `subagent`, `conditional`, `interrupt` ; builder React Flow avec palette, entry point, conditions sur edges, **PUT** persistance.
- **06** : Nœud `interrupt` + `InMemorySaver` par exécution (checkpointer dev / single-worker) ; exécution `paused` + `interrupt_state` ; `POST .../interrupt` avec `Command(resume=...)` ; événement SSE `interrupt`.
- **08 (partiel)** : Export / import agent JSON (`GET .../export`, `POST /agents/import`).
- **Schéma 08** : skills + finetune (MVP) déjà livré.
- **A3 (skills)** : validation statique (`ast`, allowlist imports, `run`, appels dangereux) + `security_validated` ; agents `skills[]` via create/update/import + UI case à cocher (détail + création) ; **exécution** : nœud `tool` avec `config.tool_name` = `skill.name` → `run()` en subprocess (`SandboxRuntime`, timeout 15s).
- **08 (suite)** : `GET /api/v1/campaigns?agent_id=` + historique red-team sur fiche agent (Δ vs run précédent) ; compteur agents distincts sur `/campaigns`.
- **CI E2E** : job `e2e` (Postgres + Redis + API + `next start` + Playwright, user seed via register) ; logs upload artifact si échec.
- **Observabilité** : middleware `http_request` structlog JSON (hors `/health`, `/docs`, OpenAPI) + tests `X-Correlation-ID`.

## Prochain

- **07** : Implémenter `modal_functions/train.py` + polling métriques + `deploy` réel.
- **08** : red-team CI dédiée, observabilité (Langfuse + **Sentry opt-in** `SENTRY_DSN`), E2E Playwright golden path (`e2e/golden-path.spec.ts` : skill → agent tool → exécution sync).


## Notes

- **HITL** : le saver mémoire est **par `execution_id`** — en multi-workers, utiliser Postgres checkpointer (`langgraph-checkpoint-postgres`) ou sticky sessions.
- Postgres **5433** ; Redis host **6380** (maps to 6379 in container).
- Hooks : `.pre-commit-config.yaml`, `CONTRIBUTING.md`.
