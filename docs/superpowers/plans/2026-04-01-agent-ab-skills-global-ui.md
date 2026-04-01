# Agent A/B, skill catalog, default agents & global UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users compare agent outputs under different parameters (temperature, top_p, etc.), browse and install a rich skill template catalog (Anthropic-style “skills” as instruction bundles), seed more useful default agents, and keep the shell / chat / playground visually cohesive with subtle motion.

**Architecture:** Skill templates stay declarative in `SKILL_TEMPLATES` (instruction + optional code + permissions). Default agents reference template names only. A/B compares two (or N) executions of the same agent graph with per-run `model_config` overrides stored on the execution or a small `compare_run` aggregate row. UI: playground page gains a “Compare variants” panel; chat slide-over reloads agents when opened so the selector is never stuck empty after auth.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Postgres, Next.js App Router, Tailwind v4 `@theme` tokens (`af-*`), existing `api()` client.

---

## File structure (ownership)

| Path | Responsibility |
|------|----------------|
| `backend/app/domain/skill_templates.py` | Canonical list of installable templates (`SKILL_TEMPLATES`). |
| `backend/app/domain/default_agents.py` | `_DEFAULT_AGENTS` seeded at registration; must only reference existing template `name`s. |
| `backend/app/api/v1/skills.py` | `GET /templates/list`, `POST /templates/{name}/install`. |
| `frontend/src/app/sandbox/page.tsx` | Playground + user skills + **template catalog** + future A/B UI. |
| `frontend/src/components/chat/ChatSlideOver.tsx` | Agent fetch + selection when panel opens. |
| `frontend/src/components/layout/AuroraBackground.tsx` | Ambient background blobs + mesh. |
| `frontend/src/app/globals.css` | Aurora keyframes, reduced-motion. |
| `frontend/src/components/layout/ToolShell.tsx` | Side nav chrome (`af-*` tokens). |
| `backend/app/api/v1/agents.py` (+ services) | New compare endpoint (planned). |
| `backend/migrations/versions/` | New migration if `compare` persistence needs a table. |

---

## Landed in repo (2026-04-01) — verify & commit

These changes are intended to be present before starting A/B work; run smoke tests and commit as `feat(frontend): …` / `feat(backend): …` in small chunks.

- [ ] **Verify:** Open chat (⌘J) after login → agent `<select>` lists all agents (not empty after late auth).
- [ ] **Verify:** Playground shows “Catalogue (templates)” with categories; “Installer” calls `POST /api/v1/skills/templates/{name}/install` and refreshes “Your skills”.
- [ ] **Verify:** New user registration seeds **7** agents including **Interview OPS Assistant** (`default_agents.py`).
- [ ] **Verify:** `GET /api/v1/templates` lists **`interview-ops-assistant`** (“Start from a template” / `/agents/new`); `POST …/create` attaches the bundled skill templates. Covered by `backend/tests/test_templates_interview_ops.py` (run with `--cov-fail-under=0` if executing that file alone).
- [ ] **Verify:** With **Google OAuth** connected (Settings) and **`GOOGLE_API_KEY`** set, **Gemini `llm` nodes** run a **tool loop** (`read_gmail`, `read_calendar`, `send_gmail`, `create_calendar_event`) so Interview OPS actually calls Gmail/Calendar APIs (not only prompt text). If `social_accounts.scopes` was empty, scopes are recovered via **Google tokeninfo**.
- [ ] **Verify:** `SKILL_TEMPLATES` includes the new instruction templates: `interview_prep`, `ops_runbook`, `slack_drafter`, `api_doc_from_code`, `security_threat_model`, `user_story_scribe`, `incident_communication`, `research_brief`, `json_schema_from_examples`.
- [ ] **Verify:** Aurora mesh + blobs animate; with OS “reduce motion”, animations collapse via existing `@media (prefers-reduced-motion)`.

---

## External reference (skill philosophy)

Anthropic documents **Agent Skills** as modular packages (metadata, instructions, optional scripts) composed for domain workflows — useful mental model when naming categories and template granularity: [Agent Skills overview](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/overview), [Skills API guide](https://docs.anthropic.com/en/docs/build-with-claude/skills-guide).

---

### Task 1: Regression test — default agents include Interview & Ops skills

**Files:**

- Modify: `backend/tests/test_agent_skills.py` (includes `test_default_agent_skill_templates_exist`)
- Read: `backend/app/domain/default_agents.py`

- [ ] **Step 1: Confirm test that template names resolve** (already added at top of `test_agent_skills.py`)

```python
from app.domain.default_agents import _DEFAULT_AGENTS
from app.domain.skill_templates import SKILL_TEMPLATES

def test_default_agent_skill_templates_exist() -> None:
    names = {t["name"] for t in SKILL_TEMPLATES}
    for agent in _DEFAULT_AGENTS:
        for skill in agent["skills"]:
            assert skill in names, f"missing template {skill!r} for agent {agent['name']!r}"
```

- [ ] **Step 2: Run test**

Run: `cd backend && pytest tests/test_agent_skills.py::test_default_agent_skill_templates_exist -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_agent_skills.py
git commit -m "test(backend): assert default agent skills match templates"
```

---

### Task 2: A/B compare — domain model & persistence (minimal)

**Files:**

- **Done:** `backend/migrations/versions/20260401_executions_compare_fields.py` — `compare_group_id`, `compare_label`, `model_config_override` on `executions` (`down_revision`: `20260331_social_scopes`).

**Recommended YAGNI shape:** add nullable columns on existing executions table:

- `compare_group_id` UUID nullable, indexed
- `compare_label` VARCHAR(32) nullable (e.g. `"A"`, `"B"`)
- `model_config_override` JSONB nullable (delta merged over agent `model_config` at run time)

- [x] **Step 1: Write migration** (see file above).

- [x] **Step 2: Run** `cd backend && alembic upgrade head`

- [ ] **Step 3: Commit** (bundle with Task 3–4 in one or more conventional commits)

```bash
git add backend/migrations/versions/20260401_executions_compare_fields.py backend/app/infrastructure/persistence/postgres/models.py
git commit -m "feat(backend): add compare metadata columns on executions"
```

---

### Task 3: A/B compare — service API

**Files:**

- Modify: `backend/app/application/services/agent_service.py` (or execution service)
- Modify: `backend/app/api/v1/agents.py`
- Create: `backend/app/api/schemas/compare_schemas.py`

**Request body (Pydantic):**

```python
from pydantic import BaseModel, Field

class CompareVariant(BaseModel):
    label: str = Field(min_length=1, max_length=32)
    model_config_override: dict  # e.g. {"temperature": 0.2}

class AgentCompareRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32000)
    variants: list[CompareVariant] = Field(min_length=2, max_length=4)
```

**Behavior:**

1. Validate `variants` length 2–4.
2. Generate `compare_group_id = uuid4()`.
3. For each variant, merge `agent.model_config` with `model_config_override` (shallow merge), then enqueue the same graph execution as normal `execute` with the same `message` / thread rules.
4. Persist each execution with `compare_group_id` + `compare_label`.

- [x] **Step 1: Write API test** — `backend/tests/test_agent_compare.py` (`run_async: false`, mock agent).

- [x] **Step 2: Implement endpoint** — `POST /api/v1/agents/{agent_id}/compare`, `AgentService.compare_executions`, `merge_agent_model_config`, persistence on `create_execution`, background merge in `_execute_background`.

- [x] **Step 3: Run** `uv run pytest tests/test_agent_compare.py -v --cov-fail-under=0`

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(backend): add agent compare executions endpoint"
```

---

### Task 4: A/B compare — playground UI

**Files:**

- **Done:** `frontend/src/lib/api.ts` — `compareAgentExecutions`, types.
- **Done:** `frontend/src/app/sandbox/page.tsx` — **dual Python panes** (`playground_a.py` / `playground_b.py`) for side-by-side skill runs; **Agent A/B lab** in a highlighted block (variants + shared message) above the skill template catalogue.

**UI sketch:**

- Section “Agent A/B” first (hero), then dual code runners, then template catalog.
- Inputs: message textarea; two JSON overrides (A/B) defaulting to `{"temperature": 0.2}` and `{"temperature": 0.9}`.
- Agent picker: `<select>` from `GET /api/v1/agents`.
- Submit → `compareAgentExecutions(..., runAsync: false)` → affiche `compare_group_id` + extrait assistant par variante.

- [x] **Step 1: Add types** in `lib/api.ts`.

- [x] **Step 2: Implement form** with loading + error states.

- [ ] **Step 3: Manual test** in browser (sync compare sur agent mock ou réel).

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(frontend): agent A/B compare panel on playground"
```

---

### Task 5: Design follow-through (design-iterator notes)

**Files:**

- Modify: `frontend/src/components/layout/ToolShell.tsx` — already aligned to `af-*`; keep **New Agent** CTA contrast.
- Optional: `frontend/src/app/layout.tsx` — ensure header uses same `af-glass-header` as dashboard.

- [ ] **Step 1:** Run design-iterator again after A/B UI exists (screenshots: dashboard, playground, chat open).

- [ ] **Step 2:** Tweak spacing tokens only (no new dependencies).

- [ ] **Step 3: Commit** if any visual diff remains.

---

## Self-review

1. **Spec coverage:** Chat agent list → Task “Landed” + `ChatSlideOver`. Skill catalog volume → new templates + sandbox catalog. Default Interview/Ops agent → `default_agents.py` + Task 1. Global design + motion → Aurora, ToolShell, chat chrome, design-iterator Task 5. A/B → Tasks 2–4.
2. **Placeholders:** None intentional; migration file name must match team convention (adjust `20260401_...` to next head).
3. **Types:** `CompareVariant.model_config_override` is a `dict`; merge function must match how `model_config` is stored on the agent entity (same keys as `execute` path).

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-01-agent-ab-skills-global-ui.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

2. **Inline execution** — batch in this session with checkpoints. REQUIRED SUB-SKILL: superpowers:executing-plans.

**Which approach?**

---

## Sources

[1] Anthropic — Agent Skills overview — https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/overview
[2] Anthropic — Using Agent Skills with the API — https://docs.anthropic.com/en/docs/build-with-claude/skills-guide
