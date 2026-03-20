# AgentForge — état GSD

## Phase courante

**07 — Fine-tuning Modal** : schéma + API `finetune_jobs` prête ; `modal_functions/` stub + README ; branchement GPU à faire.

## Fait

- **01–04** : Monorepo, auth, agents, sandbox, SSE, campaigns red-team.
- **05** : Validation Pydantic `graph_definition` ; LangGraph dynamique (edges conditionnelles par substring sur dernier message AI) ; types `subagent`, `conditional`, `interrupt` ; builder React Flow avec palette, entry point, conditions sur edges, **PUT** persistance.
- **06** : Nœud `interrupt` + `InMemorySaver` par exécution (checkpointer dev / single-worker) ; exécution `paused` + `interrupt_state` ; `POST .../interrupt` avec `Command(resume=...)` ; événement SSE `interrupt`.
- **08 (partiel)** : Export / import agent JSON (`GET .../export`, `POST /agents/import`).
- **Schéma 08** : skills + finetune (MVP) déjà livré.

## Prochain

- **07** : Implémenter `modal_functions/train.py` + polling métriques + `deploy` réel.
- **08** : Comparaison de scores, red-team CI, observabilité (Langfuse/Sentry), E2E Playwright.

## Notes

- **HITL** : le saver mémoire est **par `execution_id`** — en multi-workers, utiliser Postgres checkpointer (`langgraph-checkpoint-postgres`) ou sticky sessions.
- Postgres **5433** ; Redis host **6380** (maps to 6379 in container).
- Hooks : `.pre-commit-config.yaml`, `CONTRIBUTING.md`.
