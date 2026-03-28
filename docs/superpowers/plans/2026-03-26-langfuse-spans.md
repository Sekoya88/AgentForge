# Langfuse Enhanced Spans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Langfuse spans for tool calls and skill executions so every step of an agent run is visible as a named span in Langfuse traces, not just the LLM call.

**Architecture:** Use the `@observe` decorator from `langfuse.decorators` (available in langfuse >=2.7, which covers the project's `>=2.50.0` requirement). `@observe` auto-links child spans to the active trace context — no manual `trace_id` threading needed. The existing `CallbackHandler` in `llm_invoke.py` handles LLM call tracing already. We add `@observe`-wrapped helper functions around: (1) tool node execution in `_build_step`, (2) skill subprocess execution.

**Key constraint:** Do not modify `_run_attached_skill_code` signature — it takes `(sandbox, source_code, input_text, *, timeout_sec)`. Wrap it with a thin observed helper instead. Do not change `invoke_chat_llm` signature — it takes `(prior_messages, *, system_prompt, model_config, openai_api_key, google_api_key)`.

**Tech Stack:** `langfuse.decorators.observe`, `langfuse.decorators.langfuse_context` (both stable since langfuse v2.7)

---

### Task 1: Verify `@observe` is available in the environment

- [ ] **Step 1: Check import works**

```bash
cd backend && python -c "from langfuse.decorators import observe; print('ok')"
```

Expected: prints `ok`. If it fails, run `pip install --upgrade langfuse` — the project requires `>=2.50.0` where this is available.

---

### Task 2: Observed tool execution wrapper

**Files:**
- Modify: `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`

The tool node execution is inside `_build_step` → inner async `step(state)` function, specifically the `if ntype == "tool":` branch (around line 215). We add a thin observed async function wrapping the dispatch logic.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/infrastructure/orchestration/test_tool_span.py
"""Verify @observe-wrapped tool dispatch emits a span name matching the tool."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_observed_tool_dispatch_calls_underlying():
    """_observed_tool_dispatch must call through to the actual tool logic."""
    from app.infrastructure.orchestration.langgraph_orchestrator import _observed_tool_dispatch

    mock_handler = AsyncMock(return_value="tool_result")

    with patch("langfuse.decorators.observe", lambda **kw: lambda f: f):
        result = await _observed_tool_dispatch(
            tool_name="weather_search",
            arg="London",
            handler=mock_handler,
        )

    mock_handler.assert_awaited_once_with("London")
    assert result == "tool_result"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/infrastructure/orchestration/test_tool_span.py -v
```

Expected: `ImportError` — `_observed_tool_dispatch` does not exist yet.

- [ ] **Step 3: Add `_observed_tool_dispatch` near `_run_attached_skill_code`**

In `langgraph_orchestrator.py`, after `_run_attached_skill_code` (around line 158), add:

```python
from langfuse.decorators import langfuse_context, observe


@observe(name="tool_dispatch")
async def _observed_tool_dispatch(
    tool_name: str,
    arg: str,
    handler,
) -> str:
    """Run tool handler with Langfuse span. `handler` is an async callable(arg) -> str."""
    langfuse_context.update_current_observation(
        name=f"tool:{tool_name}",
        input={"tool_name": tool_name, "arg": arg[:500]},
    )
    result = await handler(arg)
    langfuse_context.update_current_observation(output=str(result)[:500])
    return result
```

Note: `langfuse_context` is always safe to call even when Langfuse is not configured — it's a no-op when no active trace exists.

- [ ] **Step 4: Use `_observed_tool_dispatch` in the tool branch of `_build_step`**

Inside `_build_step`, the tool node's `if ntype == "tool":` branch dispatches to various handlers. The current pattern (around line 231–270) is a series of `if tool_name == "fetch": ... elif tool_name == "echo": ... elif skill_binding is not None: ...`.

Replace the dispatch section with a single async lambda pattern:

```python
if tool_name == "fetch":
    import urllib.request

    async def _fetch_handler(input_arg: str) -> str:
        try:
            req = urllib.request.Request(input_arg, headers={"User-Agent": "AgentForge/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.read().decode("utf-8")[:500]
        except Exception as e:
            return f"Fetch Error: {e}"

    handler = _fetch_handler

elif tool_name == "echo":
    async def _echo_handler(input_arg: str) -> str:
        return f"Echo: {input_arg}"

    handler = _echo_handler

elif tool_name == "retrieve":
    top_k = int(cfg.get("top_k") or 5)

    async def _retrieve_handler(input_arg: str) -> str:
        if knowledge_search is not None:
            return await knowledge_search(input_arg, top_k)
        return "[retrieve] Knowledge search is not available for this execution."

    handler = _retrieve_handler

elif skill_binding is not None:
    if skill_binding.skill_type == "instruction":
        async def _instruction_handler(input_arg: str) -> str:  # noqa: F811
            return skill_binding.instructions or "(no instructions)"

        handler = _instruction_handler
    else:
        if not skill_binding.security_validated:
            await bus.emit(
                "skill_notice",
                {"tool_name": tool_name, "message": "Skill is not marked security_validated"},
            )

        async def _skill_handler(input_arg: str) -> str:  # noqa: F811
            return await _run_attached_skill_code(
                sandbox,
                skill_binding.source_code,
                input_arg,
                timeout_sec=skill_timeout_sec,
            )

        handler = _skill_handler
else:
    async def _stub_handler(input_arg: str) -> str:  # noqa: F811
        return f"[tool:{tool_name}] executed with input '{input_arg}' (stub)."

    handler = _stub_handler

res = await _observed_tool_dispatch(tool_name=tool_name, arg=arg, handler=handler)
```

Then keep the existing `msg = AIMessage(...)` and `bus.emit("tool_result", ...)` lines unchanged.

- [ ] **Step 5: Run the test**

```bash
cd backend && pytest tests/infrastructure/orchestration/test_tool_span.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full backend tests to verify no regressions**

```bash
cd backend && pytest tests/ -v --tb=short -q
```

Expected: all existing tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/infrastructure/orchestration/langgraph_orchestrator.py \
        backend/tests/infrastructure/orchestration/test_tool_span.py
git commit -m "feat(observability): add Langfuse @observe span around tool dispatch in orchestrator"
```

---

### Task 3: Observed agent run wrapper

**Files:**
- Modify: `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`

The `LangGraphAgentOrchestrator.run()` method is the entry point for all agent executions (around line 456). Wrapping it with `@observe` gives a root span that all tool and LLM spans nest under.

- [ ] **Step 1: Add `@observe` to `run()` method**

Find the `run` method signature on `LangGraphAgentOrchestrator`:

```python
async def run(
    self,
    agent: Agent,
    input_messages: list[BaseMessage],
    ...
) -> str:
```

Add the decorator (import is already added in Task 2):

```python
@observe(name="agent_run")
async def run(self, agent: Agent, input_messages: list[BaseMessage], ...) -> str:
    langfuse_context.update_current_observation(
        input={"agent_id": str(agent.id), "agent_name": agent.name},
        metadata={"model_config": agent.llm_model_config},
    )
    # ... rest of existing method unchanged ...
```

Note: `langfuse_context.update_current_observation` is safe to call even without Langfuse configured.

- [ ] **Step 2: Run full backend tests**

```bash
cd backend && pytest tests/ -v --tb=short -q
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/app/infrastructure/orchestration/langgraph_orchestrator.py
git commit -m "feat(observability): add Langfuse @observe root span on agent_run"
```

---

### Task 4: End-to-end verification

- [ ] **Step 1: Configure Langfuse (free cloud)**

Go to https://cloud.langfuse.com, create a project, get keys. Add to `backend/.env`:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

- [ ] **Step 2: Run an agent execution with a skill**

```bash
cd backend && uvicorn app.main:app --reload
# Via UI: create a skill, attach to agent, execute agent with a message
```

- [ ] **Step 3: Verify in Langfuse dashboard**

Open Langfuse → Traces. Expect to see:
- Root span: `agent_run` with `agent_id` in metadata
  - Child: `tool:weather_search` (or whichever tool ran) with input/output
  - Child: LLM span (from existing `CallbackHandler`)

- [ ] **Step 4: Commit any adjustments**

```bash
git add -p
git commit -m "fix(observability): adjust Langfuse span names based on verification"
```
