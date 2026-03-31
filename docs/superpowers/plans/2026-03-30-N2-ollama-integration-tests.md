# Phase N2 — Tests d'intégration LocalAgent × Ollama

> **Statut : implémenté (codebase)** — Fichiers sous `sdk/tests/integration/` ; fixture `ollama_model` résout un modèle installé (`OLLAMA_MODEL` ou premier tag `/api/tags`). Exécuter : `cd sdk && pytest tests/integration/ -m integration -v` (skip si Ollama absent ou aucun modèle).

> **For agentic workers:** `superpowers:subagent-driven-development` ou `superpowers:executing-plans` ; TDD / verification skill avant clôture.

## Objectif

Valider le SDK Python **avec un vrai Ollama** local : `invoke` / `astream`, tools, edges conditionnels, policy, export/reload.

## Prérequis

- Ollama sur `localhost:11434`, modèle léger (ex. `llama3.2`).
- Marker pytest `integration` + skip si `GET /api/tags` échoue.

## Livrables (rappel spec)

| Fichier cible | Scénario |
|---------------|----------|
| `sdk/tests/integration/test_local_agent_llm.py` | 1 nœud LLM Ollama → `AIMessage` |
| `sdk/tests/integration/test_local_agent_streaming.py` | `astream()` ≥ 1 événement utile |
| `sdk/tests/integration/test_local_agent_tool.py` | LLM → tool instruction → LLM |
| `sdk/tests/integration/test_local_agent_conditional.py` | Routing `contains` |
| `sdk/tests/integration/test_local_agent_custom_node.py` | Plugin `@node("echo")` |
| `sdk/tests/integration/test_local_agent_policy.py` | `max_steps=1` |
| `sdk/tests/integration/test_builder_export_reload.py` | export JSON → reload → `invoke` |

## Critères d'acceptation

- `pytest sdk/tests/integration/ -m integration` vert avec Ollama up ; skip propre sinon.
- Aucun appel réseau hors localhost Ollama dans ces tests.
