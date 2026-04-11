# AgentForge Technical Hardening & Scale Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan **track-by-track**. Steps use checkbox (`- [ ]`) syntax for tracking. Treat each **Phase** as a mergeable slice; commit after each phase.

**Goal:** Reduce production risk (SSE, sandbox, migrations), improve maintainability of orchestration, add operational headroom (scheduling, memory fallback, observability), and harden multi-tenant boundaries—without rewriting the whole stack.

**Execution status (2026-04-11):** Tracks **P0–P3** below are implemented in-repo unless marked *partial*. Re-run grep/`wc` before the next execution pass if `dev` diverged.

**Architecture:** Keep **FastAPI + SQLAlchemy async + Alembic + LangGraph**; evolve **infrastructure** (SSE client, sandbox factory, worker entrypoints) and **slice** `langgraph_orchestrator.py` by responsibility. Prefer **ports** (`app/domain/ports/*`) for new implementations (memory, rate limits) so tests stay swappable.

**Tech Stack:** Python 3.12+, FastAPI, Redis (streams/SSE), PostgreSQL + pgvector, LangGraph/LangChain, Next.js frontend, pytest, Alembic.

---

## Codebase context (local repository — vetted)

| Area | Location | Notes (Apr 2026) |
|------|----------|------------------|
| SSE server | `backend/app/api/sse.py` | **Done:** `resume_after` + SSE `id:` lines; `after_id` query on agent/forge/sandbox streams. |
| SSE client | `frontend/src/lib/sse.ts` | **Done:** `consumeSsePathWithRetry` / backoff + `after_id` when ids present. |
| Sandbox | `backend/app/config.py` (`SANDBOX_MODE`), `backend/app/dependencies.py` | `subprocess` (default) vs `docker`; `SubprocessSandboxRuntime` runs `sys.executable -c` with timeout—no seccomp/cgroups. |
| Docker image | `backend/Dockerfile` + `scripts/docker_entrypoint.sh` | **Done:** Alembic `upgrade head` then uvicorn; prod compose uses `UVICORN_EXTRA_ARGS`. |
| Orchestrator | `backend/app/infrastructure/orchestration/langgraph_orchestrator.py` | ~1736 lines; monolith for graph build + node steps + SSE-related helpers. |
| Schedules | `backend/app/infrastructure/scheduling/tick.py` | **Done:** `claim_due_schedules` + `FOR UPDATE SKIP LOCKED` in one txn; still no external queue. |
| Memory | `noop_memory_store.py`, `pgvector_memory_store.py`, `agent_service` | **Done:** `DISABLE_PGVECTOR_MEMORY` → noop + graph `__memory_store__` / user / agent injection. |
| API tests | `backend/tests/api/` | 4 files (`test_rate_limiting.py`, `test_finetune_inference_stream.py`, `test_new_endpoints.py`, `test_speech_voice_samples.py`). |
| Workspace | `backend/migrations/versions/20260408_workspace_members.py`, `workspace_member_repo.py` | App-level membership; **no** Postgres RLS found in quick grep—audit required for every query path. |
| Rate limit | `slowapi` + workspace middleware | Per-user/workspace patterns; no dedicated per-IP global limiter in grep scope. |

**Freshness:** Table reflects current tree; re-run `rg` / `wc` before execution if branch diverged.

**Gaps vs org-wide `/codebase-context`:** This plan does **not** include Glean/code_search across other repos or employee directory—only AgentForge.

---

## File map (high level)

| Initiative | Likely create | Likely modify |
|------------|---------------|----------------|
| P0 SSE | `frontend/src/lib/sseReconnect.ts` (or extend `sse.ts`) | `frontend/src/lib/sse.ts`, callers in agents/builder/forge/sandbox pages |
| P0 Sandbox | `docs/runbooks/sandbox.md`, optional `backend/scripts/verify_sandbox.sh` | `subprocess_sandbox.py`, `docker_sandbox.py`, `config.py`, `README.md` |
| P0 Migrations | `backend/scripts/docker_entrypoint.sh` | `backend/Dockerfile`, `docker-compose.prod.yml` |
| P1 Orchestrator split | `backend/app/infrastructure/orchestration/graph_compile.py`, `node_steps.py`, … | `langgraph_orchestrator.py` (shrink re-exports) |
| P1 Memory | `in_memory_memory_store.py` (dev) or `noop_memory_store.py` | `dependencies.py`, `config.py` |
| P1 Scheduling | optional `redis_lock.py` | `tick.py`, `main.py` lifespan |
| P2 Observability | — | `config.py`, span emitters, `README.md` |
| P2 API tests | `tests/api/test_executions_*.py`, etc. | — |
| P3 Workspace | `docs/security/workspace-audit-checklist.md` | repos, agent routes, middleware |
| P3 Rate limit | `middleware/ip_rate_limit.py` | `main.py`, `config.py` |

---

## Track P0 — Critical production robustness

### Phase P0-A: SSE resilience (server + client contract)

**Files:**

- Modify: `backend/app/api/sse.py` (optional: `LAST_ID` resume via `XREAD` from client id)
- Modify: `frontend/src/lib/sse.ts`
- Modify: each caller: grep `consumeSsePath|consumeExecutionSse|consumeForgeSse|consumeFinetuneSse`
- Test: `backend/tests/test_sse_resume.py` (+ existing `test_streams.py`).

- [x] **Step 1: Document current SSE contract** in `docs/api/sse-execution-stream.md` (event types: `complete`, `error`, ping; Redis key pattern from `redis_execution_stream.py`).

- [x] **Step 2: Add optional `after_id` query** on execution stream route (`agents.py`, `forge.py`, `sandbox.py`) so `XREAD` resumes after last seen Redis ID. Pseudocode server:

```python
# In stream handler: parse query last_id, default "0-0"
# Pass to redis_stream_sse(..., start_id=last_id)
```

- [x] **Step 3: Extend `redis_stream_sse`** with `resume_after` + SSE `id:` lines (replaces hardcoded full replay only when no cursor).

- [x] **Step 4: Frontend — implement `consumeSsePathWithRetry`** in `frontend/src/lib/sse.ts`:

```typescript
export async function consumeSsePathWithRetry(
  path: string,
  onLine: (event: string, data: string) => void,
  opts?: { maxRetries?: number; baseDelayMs?: number; signal?: AbortSignal },
): Promise<void> {
  const maxRetries = opts?.maxRetries ?? 5;
  let attempt = 0;
  let lastEventId: string | undefined;
  while (attempt <= maxRetries) {
    try {
      const url =
        (path.startsWith("http") ? path : `${BASE}${path}`) +
        (lastEventId ? `?after_id=${encodeURIComponent(lastEventId)}` : "");
      // fetch with Authorization; parse SSE; update lastEventId from redis id if exposed in payload
      await consumeSseOnce(url, onLine, opts?.signal);
      return;
    } catch {
      attempt++;
      await new Promise((r) => setTimeout(r, opts?.baseDelayMs ?? 500 * 2 ** (attempt - 1)));
    }
  }
  throw new Error("SSE: max retries exceeded");
}
```

(`consumeSsePath` delegates to retry wrapper; callers unchanged.)

- [x] **Step 5: Wire retry wrapper** — default `consumeSsePath` uses retry for all existing callers.

- [ ] **Step 6: Commit** *(squash with other roadmap commits or keep separate `fix(sse): …`)*

```bash
git add backend/app/api/sse.py backend/app/api/v1/*.py frontend/src/lib/sse.ts docs/api/sse-execution-stream.md
git commit -m "fix(sse): optional resume id and client retry backoff"
```

---

### Phase P0-B: Sandbox strategy & hardening

**Files:**

- Modify: `backend/app/infrastructure/sandbox/subprocess_sandbox.py`
- Modify: `backend/app/infrastructure/sandbox/docker_sandbox.py`
- Modify: `backend/app/config.py`, `backend/README.md` or root `README.md`
- Create: `docs/runbooks/sandbox-production.md`

- [x] **Step 1: Write runbook section** stating: **default dev = subprocess**; **prod recommendation = `SANDBOX_MODE=docker`** with link to Docker socket requirements.

- [x] **Step 2: Subprocess hardening (minimal YAGNI)**
  - Run child with `cwd` in a temp dir per invocation.
  - Set `preexec_fn`-equivalent not available on asyncio—use **`sys.executable` only** and deny custom interpreter (already true).
  - **Document** in runbook that Docker is the real isolation boundary (no `prlimit` in-tree).

- [x] **Step 3: Add integration test** `backend/tests/test_sandbox_mode_factory.py`:

```python
import pytest
from app.dependencies import build_sandbox_runtime
from app.config import Settings

def test_sandbox_factory_selects_docker():
    s = Settings(_env_file=None, SANDBOX_MODE="docker")  # type: ignore
    rt = build_sandbox_runtime(s)
    assert rt.__class__.__name__ == "DockerSandboxRuntime"

def test_sandbox_factory_default_subprocess():
    s = Settings(_env_file=None, SANDBOX_MODE="subprocess")  # type: ignore
    rt = build_sandbox_runtime(s)
    assert rt.__class__.__name__ == "SubprocessSandboxRuntime"
```

- [x] **Step 4: CI matrix** optional — documented skip in `docs/runbooks/sandbox-production.md`.

- [ ] **Step 5: Commit** *(combine with other phases or `docs(runbooks): …`)*

---

### Phase P0-C: Migrations at deploy boot

**Files:**

- Modify: `backend/Dockerfile`
- Create: `backend/scripts/docker_entrypoint.sh` (executable)

- [x] **Step 1: Add entrypoint script** `backend/scripts/docker_entrypoint.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
python -m alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [x] **Step 2: Dockerfile** change:

```dockerfile
COPY scripts/docker_entrypoint.sh ./scripts/docker_entrypoint.sh
RUN chmod +x ./scripts/docker_entrypoint.sh
CMD ["./scripts/docker_entrypoint.sh"]
```

- [x] **Step 3: Document idempotency** — `backend/README.md` + Dockerfile comment; prod compose aligned.

- [x] **Step 4: Commit** `build(backend): run alembic upgrade before uvicorn in docker` *(done on branch)*

---

## Track P1 — Scalability & maintainability

### Phase P1-A: Split `langgraph_orchestrator.py` (incremental, no behavior change)

**Target modules (suggested):**

- `backend/app/infrastructure/orchestration/graph_state.py` — `_State`, message dict helpers
- `backend/app/infrastructure/orchestration/graph_compile.py` — `_compile_state_graph`, routing
- `backend/app/infrastructure/orchestration/node_builders.py` — `_build_step` and node type branches (or split by node family: `tool_node.py`, `llm_node.py`, …)
- `backend/app/infrastructure/orchestration/langgraph_orchestrator.py` — thin `LangGraphAgentOrchestrator` delegating

- [x] **Step 1: Extract pure functions** — **`graph_state.py`** (`GraphState`, message helpers); orchestrator imports aliases. *Further splits (`graph_compile`, node builders) still open.*

- [ ] **Step 2: Commit per extraction** (frequent commits).

---

### Phase P1-B: Memory store fallback

**Files:**

- Create: `backend/app/infrastructure/memory/noop_memory_store.py` implementing `MemoryStore` port (returns empty recall / no-op save)
- Modify: `backend/app/application/services/agent_service.py`, `api/v1/memory.py`, `config.py` — explicit `DISABLE_PGVECTOR_MEMORY` flag (no silent DB-failure fallback).

- [x] **Step 1: Write test** `backend/tests/test_memory_fallback.py`:

```python
import pytest
from app.infrastructure.memory.noop_memory_store import NoopMemoryStore

@pytest.mark.asyncio
async def test_noop_recall_empty():
    m = NoopMemoryStore()
    out = await m.recall(user_id=..., agent_id=..., query_embedding=[0.0] * 8, top_k=3)
    assert out == []
```

- [x] **Step 2: Implement `NoopMemoryStore`**.

- [x] **Step 3: Wire** `DISABLE_PGVECTOR_MEMORY` into `agent_service` graph extras + `memory` router.

- [ ] **Step 4: Commit** `feat(memory): optional noop store when pgvector disabled`

---

### Phase P1-C: Scheduling — lease / lock (reduce double-fire)

**Files:**

- Modify: `backend/app/infrastructure/scheduling/tick.py`
- Possibly: `backend/app/infrastructure/persistence/postgres/agent_repo.py` (`list_due_schedules`, `claim_schedule`)

- [x] **Step 1: Design** — `PostgresAgentRepository.claim_due_schedules` locks + updates `next_run_at` in one flush.

- [ ] **Step 2: Test** concurrent `run_schedule_tick_once` *(optional follow-up; no dedicated test yet)*.

- [ ] **Step 3: Commit** `fix(schedules): claim due rows with row-level lock`

---

## Track P2 — Observability & API coverage

### Phase P2-A: Unified observability defaults

**Files:**

- Modify: `backend/app/config.py`, `backend/app/infrastructure/observability/*`

- [x] **Step 1: At startup log** effective `OBSERVABILITY_BACKEND` + key presence flags (`main.py` lifespan structlog).

- [x] **Step 2: When `none` / `off`**, `_get_observability_callbacks` returns `[]` (unchanged empty list contract).

- [ ] **Step 3: Commit** `chore(obs): clarify backend and missing-key behavior`

---

### Phase P2-B: API integration tests (prioritized endpoints)

Create tests under `backend/tests/api/`:

| File | Focus |
|------|--------|
| `test_auth_refresh_flow.py` | login, refresh, 401 without token |
| `test_executions_stream_contract.py` | stream headers, terminal event |
| `test_webhook_hmac.py` | HMAC vector for delivery payload shape |

*First wave added:* `test_auth_refresh_flow.py`, `test_executions_stream_contract.py`, `test_webhook_hmac.py`.

---

## Track P3 — Security & platform

### Phase P3-A: Multi-workspace isolation audit

**Files:**

- Read: all `agent_repo` / `execution` queries for `user_id` filter
- Create: `docs/security/workspace-isolation-audit.md`

- [x] **Step 1: Grep** `where.*user_id` and `workspace` in `backend/app/api` + `postgres/*_repo.py`.

- [x] **Step 2: Table** high-level surfaces → OK / follow-up in `docs/security/workspace-isolation-audit.md`.

- [ ] **Step 3: If gaps** → fix with tests; consider Postgres RLS as **future** phase (bigger migration).

---

### Phase P3-B: Global / IP rate limiting

**Files:**

- Modify: `backend/app/main.py`, new middleware file

- [x] **Step 1: SlowAPI + IP** — global limiter uses `get_remote_address`; auth routes already `@limiter.limit("10/minute")` on login/register (`auth.py`). Docstring in `rate_limit.py`.

- [x] **Step 2: Test** — `tests/api/test_rate_limiting.py` covers login/register 429.

- [ ] **Step 3: Commit** *(no code change required beyond docs if desired)*

---

## Recommended execution order (merged priorities)

1. **P0-C** — Alembic at Docker boot (fast, high deploy ROI).
2. **P0-B** — Sandbox runbook + factory test + prod default `docker` in example compose.
3. **P0-A** — SSE resume + client retry (pairs server + frontend).
4. **P1-A** — Orchestrator extraction (ongoing, parallelizable after tests green).
5. **P1-C** — Schedule claiming (before horizontal scale).
6. **P1-B** — Memory noop flag.
7. **P2-B** + **P2-A** — Tests + observability clarity.
8. **P3-A** + **P3-B** — Security audit + IP limits.

---

## Self-review (author checklist)

1. **Spec coverage:** Each user bullet (SSE, sandbox, migrations, monolith, memory, scheduling tick, observability, API tests, workspace, rate limit) maps to a **Phase** above. ✅
2. **Placeholder scan:** No `TBD` / empty implementation steps; code blocks are concrete starters. ✅
3. **Type consistency:** Public `build_sandbox_runtime` in `app.dependencies`; tests import that. ✅

---

## Execution handoff

**Plan complete and saved to** `docs/superpowers/plans/2026-04-10-agentforge-technical-roadmap.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per **Phase** (P0-C, then P0-B, …), review between phases. **Sub-skill:** `superpowers:subagent-driven-development`.

2. **Inline execution** — Run phases in this session with checkpoints. **Sub-skill:** `superpowers:executing-plans`.

**Which approach do you want?** (Reply `1` or `2`, or name a single phase to start—e.g. `P0-C only`.)
