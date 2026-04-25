# AgentForge Graph (AFG) contract

The canonical agent workflow shape is JSON stored in `agents.graph_definition` (and version snapshots). This document is the human-readable contract; the server validates with Pydantic (`GraphDefinitionValidated`).

## Schema version

| Field                    | Type   | Default | Description                                      |
|--------------------------|--------|---------|--------------------------------------------------|
| `graph_schema_version`   | string | `"1.0"` | AFG revision. Bump when breaking node/edge rules. |

Clients SHOULD send `graph_schema_version` on write. Readers MUST accept older versions and normalize missing values to `"1.0"`.

## Graph shape

| Field             | Type        | Required | Description                                |
|-------------------|-------------|----------|--------------------------------------------|
| `nodes`           | object[]    | yes      | At least one node; each has `id`, `type`, `config`. |
| `edges`           | object[]    | no       | `from`, `to`, optional `condition`, `condition_type`. |
| `entry_point`     | string      | yes      | Must match a node `id`.                    |
| `parallel_nodes`  | string[]    | no       | Hint for parallel execution.               |

## Node types (built-in)

- `llm` — LLM call with `config.prompt` (and provider-specific options).
- `tool` — Registry skill / built-in tool; `config.tool_name` matches skill name.
- `subagent` — Delegates to another agent graph.
- `conditional` — Routing helper (often used with edges).
- `interrupt` — Human-in-the-loop pause (`interrupt_config` on agent).

## YAML authoring (optional)

For git-friendly sources, use `.afg.yaml` and compile to JSON:

```bash
agentforge compile my_agent.afg.yaml -o export.json
```

The JSON `graph_definition` block remains the single source of truth in the API and database.

## Related code

- Backend: `backend/app/domain/graph_definition.py`
- SDK validation: `sdk/src/agentforge/graph_validate.py`, CLI `agentforge validate`
