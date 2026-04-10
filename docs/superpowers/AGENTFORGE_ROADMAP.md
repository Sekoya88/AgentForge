# AgentForge — Roadmap 2026

> **Last updated:** 2026-04-10 · Based on full codebase analysis.
> **Status legend:** `[SHIPPED]` fully working · `[PARTIAL]` code exists, gaps noted · `[PLANNED]` not started

**In-app guide:** open **`/walkthrough`** in the web UI for condensed “try these flows” steps (mirrors the scenarios below).

AgentForge is a full-stack workbench to **design, run, harden, and export LLM agents** built as visual graphs. You drag nodes onto a canvas, attach Python skills, connect knowledge bases, run red-team campaigns, and iterate until the agent is production-ready — then export it as JSON, YAML, Python, or Docker.

---

## What you can build TODAY

Five real scenarios you can test right now against a running AgentForge instance.

---

### Use Case 1 — Customer Support Agent with RAG

**Goal:** An agent that answers questions about your product docs without hallucinating.

**Steps:**

1. Go to `/knowledge` → upload your docs (plain text or markdown files)
2. Go to `/agents/new` → choose "Blank" template
3. In the builder, add two nodes:
   - `Retrieve` node (tool: `retrieve`, top_k: 5) — pulls relevant chunks from your knowledge base
   - `LLM` node (provider: `anthropic` or `openai`) — system prompt: *"Answer using only the provided context. If unsure, say so."*
4. Connect: `START → Retrieve → LLM → END`
5. Click "Run" → type a question about your docs → watch the agent retrieve + answer
6. Check `/executions` to see the full trace with token usage

**What to verify:**
- The LLM response cites content from your uploaded docs
- Execution trace shows the retrieve node returning chunks
- Try a question outside your docs — the agent should say it doesn't know

**Limitations today:** very large PDFs or JS-heavy / auth-walled URLs may ingest poorly; prefer clean text, markdown, or static HTML pages. Use **`POST /api/v1/knowledge/ingest-url`** or the Knowledge UI where available.

---

### Use Case 2 — Scheduled Digest Agent

**Goal:** An agent that runs every morning, fetches data, summarizes it, and posts a webhook notification.

**Steps:**

1. Go to `/agents/new` → choose "Blank" template
2. Build a 2-node graph:
   - `Tool` node (tool: `web_search`, query: `"AI news today"`)
   - `LLM` node — system prompt: *"Summarize these search results in 5 bullet points."*
3. Save the agent
4. Go to the agent detail page → "Schedules" tab → create a cron: `0 8 * * *` (8am daily)
5. Go to `/settings` → Webhooks → add a webhook URL for **`execution.completed`** (dot-separated event name in API payloads)
6. Wait for the schedule to fire (or click "Run now") → check your webhook endpoint for the payload

**What to verify:**
- Schedule appears in the agent's schedule list with `next_run_at`
- After execution, your webhook receives a POST with `execution_id`, `output`, and `status`
- `/executions` shows the execution with `trigger: schedule`

**Limitations today:** the Settings UI only lets users register **`execution.completed`** and **`campaign.completed`**. The backend may still schedule **`execution.started`** and **`execution.failed`** deliveries for users who have matching subscription rows; extend the API/UI if you need first-class registration for those events.

---

### Use Case 3 — Voice Assistant

**Goal:** A voice-in, voice-out assistant that transcribes speech, reasons, and responds with audio.

**Steps:**

1. Go to `/agents/new` → choose the **"Voice Assistant"** template (pre-built ASR → LLM → TTS)
2. In the builder, verify the graph: `ASR node → LLM node → TTS node`
3. Configure the TTS node: pick `openai` or `elevenlabs` as provider (requires API key in `/settings`)
4. Save the agent
5. Test via the API:

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/execute/audio \
  -H "Authorization: Bearer {your_token}" \
  -F "audio=@your_voice.wav"
```

6. The response contains `audio_output` (base64 WAV) — decode and play it

**What to verify:**
- ASR node transcribes your audio correctly (check execution trace)
- LLM node receives the transcription as input
- TTS node returns audio in the response
- Full round-trip latency visible in the execution detail

**Limitations today:** Real-time streaming audio not yet supported (request/response only).

---

### Use Case 4 — Red-Team Your Agent

**Goal:** Automatically probe your agent for prompt injection, jailbreaks, and unsafe outputs before shipping.

**Steps:**

1. Build any agent (e.g., the RAG agent from Use Case 1)
2. Go to `/campaigns` → "New Campaign"
3. Select your agent, choose attack categories (prompt injection, jailbreak, PII extraction)
4. Click "Run Campaign" — this triggers the Promptfoo engine against your agent
5. Watch the campaign progress in real time
6. When complete, review the report: per-category scores, failing prompts, and the security score written back to the agent

**What to verify:**
- Campaign runs and produces a score (0–100)
- The agent's detail page shows an updated `security_score`
- The report lists which attack prompts succeeded and which were blocked
- `campaign_completed` webhook fires if you have one configured

**Tip:** Run a campaign before every major agent update. The security score is stored per agent version.

---

### Use Case 5 — Fine-Tune and Deploy Your Own Model

**Goal:** Collect high-quality examples from your agent's executions, fine-tune a model on GPU, and swap it in.

**Steps:**

1. Run your agent on 20–50 real inputs (Use Cases 1–3 are good sources)
2. Go to `/executions` → for each execution, click "Mark as example" to flag good outputs
3. Go to `/finetune` → "New Job" → select `text_sft` modality, pick your base model
4. The system auto-populates the dataset from your flagged examples
5. Click "Start Training" — this triggers a Modal GPU job (A100)
6. Monitor training progress in the finetune detail page
7. When complete, the model is auto-deployed under the `shadow` alias
8. Go to your agent → update the LLM node provider to `finetuned` → test
9. If satisfied, promote the alias to `production`

**What to verify:**
- Training job appears with `status: running` in `/finetune`
- Loss metrics update during training
- After completion, `shadow` alias is available as a provider option
- Agent executions with `finetuned` provider show lower latency than the base model

**Current status:** Modal training code is a stub — this flow is partially wired. See Task 1.2.

---

## Current State — What's Shipped

### Backend `[SHIPPED]`

| Feature | Details |
|---------|---------|
| LangGraph orchestrator | 7 node types: `llm`, `tool`, `conditional`, `interrupt`, `subagent`, `asr`, `tts` |
| Forge assistant | Multi-provider (Anthropic, OpenAI, Gemini), 8 built-in tools, multi-tab UI |
| Hybrid RAG | BM25 + pgvector semantic search, RRF fusion, structural chunking with heading context |
| Red-team campaigns | Promptfoo real engine + Mock engine, security score written to agent |
| Fine-tuning | Modal integration wired (text_sft, whisper, tts_voice), auto-deploy shadow alias |
| Schedules | Cron worker, full CRUD, ticks every 60s |
| Speech | ASR (Whisper + finetuned HTTP), TTS (OpenAI + ElevenLabs + finetuned HTTP), audio execute endpoint |
| Observability | Langfuse `@observe` on orchestrator + forge, span emitter for all SSE events |
| Webhooks | Outbound delivery for `execution_completed` and `campaign_completed` |
| Agent versioning | Snapshots, aliases (production/staging), rollback, diff |
| Context management | Sliding window + automatic LLM compression |
| Execution policy | Tool allowlist/denylist, pattern blocking, human approval, max_cost, max_steps |

### Frontend `[SHIPPED]`

| Feature | Details |
|---------|---------|
| Visual builder | React Flow, all 7 node types |
| Forge UI | Multi-tab, slash commands, streaming tokens, activity toasts |
| Chat | Multi-agent, multi-conversation, slide-over + fullscreen, SSE activity animations |
| SSE animations | `AgentStepChips`, `AgentToastStack`, `AgentActivityIcon` |
| Pages | dashboard, agents, builder, skills, knowledge, finetune, campaigns, executions, sandbox, settings, profile |

### SDKs `[SHIPPED]`

| Package | Status |
|---------|--------|
| `agentforge` (Python SDK) | `[SHIPPED]` — `LocalAgent`, `AgentBuilder`, full CLI, speech providers |
| `@agentforge/sdk` (TypeScript) | `[SHIPPED]` — `AgentClient`, `AgentBuilder`, CLI, OpenAPI types |
| `agentforge-client` (Python HTTP client) | `[SHIPPED]` — full API coverage: agents, schedules, skills, knowledge, campaigns, finetune, forge, executions, webhooks, generation, memory, budget, pii, prompt_optimizer, export, workspace |
| `agentforge-mcp` | `[SHIPPED]` — 18 tools: agents CRUD, execute, export, executions, skills, knowledge, campaigns, forge, conversations, memory, webhooks, budget, finetune, analytics, schedules |

### Known Gaps

| Gap | Impact |
|-----|--------|
| Modal training code is a stub | Fine-tune flow (Use Case 5) not fully functional |
| No PDF/URL ingestion | Knowledge base limited to plain text |
| No long-term agent memory | Agents forget between sessions (memory infrastructure exists) |
| Only 2 webhook events | Can't react to failures, schedule fires, or agent updates |
| Body font is `font-mono` | All UI text reads like a terminal — fatiguing for long sessions |
| No empty states | New users see blank pages with no guidance |
| No onboarding flow | First-run experience is a blank dashboard |
| Nodes visually undifferentiated | Complex graphs are hard to read at a glance |
| Dashboard shows counts only | Can't answer "what happened?" or "do I need to act?" |

---

## Sprint Roadmap

---

### Sprint 1 — Complete the Foundation ✅ `[SHIPPED]`

**Goal:** Everything that's wired but broken or incomplete gets finished.

---

#### Task 1.1 — MCP Server: Expose the full API `[SHIPPED]`

> **Why it matters:** Right now Cursor agents and Claude Desktop can only list and execute agents. They can't manage skills, search knowledge, or run campaigns. This makes AgentForge a black box to AI assistants.

**Current state:** `mcp-server/src/agentforge_mcp/server.py` exposes only `list_agents` and `execute_agent`.

**Add to `mcp-server/src/agentforge_mcp/server.py`:**

```python
# Skills
@mcp.tool() async def list_skills() -> list[dict]: ...
@mcp.tool() async def create_skill(name, source_code, description) -> dict: ...

# Knowledge
@mcp.tool() async def search_knowledge(query: str, top_k: int = 5) -> list[str]: ...
@mcp.tool() async def ingest_knowledge(text: str, source_title: str) -> dict: ...

# Campaigns
@mcp.tool() async def launch_campaign(agent_id: str, config: dict) -> dict: ...
@mcp.tool() async def get_campaign_report(campaign_id: str) -> dict: ...

# Forge
@mcp.tool() async def forge_chat(message: str, provider: str = "anthropic") -> str: ...

# Executions
@mcp.tool() async def get_execution(execution_id: str) -> dict: ...
@mcp.tool() async def list_executions(agent_id: str, limit: int = 10) -> list[dict]: ...

# Conversations
@mcp.tool() async def create_conversation(agent_id: str) -> dict: ...
@mcp.tool() async def get_conversation_messages(agent_id: str, conv_id: str) -> list[dict]: ...
```

**Tasks:**
1. Implement the 11 missing tools
2. Add auth token in HTTP headers (`Authorization: Bearer {token}`)
3. Publish to npm: `@agentforge/mcp`
4. Document in `mcp-server/README.md` with Cursor/Claude config

---

#### Task 1.2 — Fine-tuning Modal: Write the real training code `[SHIPPED]`

> ⚠️ Requires live Modal GPU environment — code structure is in place, end-to-end testing requires GPU infra.

> **Why it matters:** Use Case 5 (fine-tune + deploy) is the highest-value differentiator of AgentForge. Right now it's wired in the UI but the GPU training code is a commented stub.

**Current state:** `modal_functions/train.py` is entirely commented out. `FinetuneService` calls `modal.Function.from_name("agentforge-finetune", "train_model")` but this function doesn't exist in prod.

**Files:**
- `backend/modal_functions/train.py` — implement with Unsloth/TRL
- `backend/modal_functions/train_speech.py` — ASR/TTS fine-tuning (currently commented)

**Tasks:**
1. Implement `train_model()` Modal with Unsloth QLoRA (text_sft) on A100 GPU
2. Implement `train_speech_model()` (Whisper + xtts/bark for tts_voice)
3. Stream loss logs to DB via Modal callback → FastAPI webhook
4. Test full flow: upload JSONL dataset → trigger → deploy → inference stream

---

#### Task 1.3 — SDK Client Python: Cover the full API `[SHIPPED]`

> **Why it matters:** Anyone automating AgentForge workflows (CI/CD, scripts, notebooks) is blocked on 80% of the API surface.

**Current state:** `sdk-client/` covers only agents, schedules, and a few speech routes.

**Missing modules in `sdk-client/src/agentforge_client/`:**

```python
skills.py      # CRUD skills
knowledge.py   # ingest, search, list_sources, delete
campaigns.py   # launch, get, report, delete
finetune.py    # create, get, list, deploy, trigger
forge.py       # conversations + execute + stream
executions.py  # list, get, feedback, interrupt
webhooks.py    # CRUD webhooks
generation.py  # generate_agent, generate_skill
```

**Tasks:**
1. Create one module per domain
2. Cover all endpoints from `backend/app/api/v1/`
3. Generate types from `openapi/openapi.json`
4. Publish to PyPI: `pip install agentforge-client`

---

#### Task 1.4 — Knowledge: PDF and URL Ingestion `[SHIPPED]`

> **Why it matters:** Most real knowledge bases are PDFs (docs, manuals, reports) or websites. Text-only ingestion severely limits Use Case 1.

**Current state:** Only `POST /knowledge/ingest` (raw text) and `POST /knowledge/upload` (file) are implemented. No PDF parsing, no web crawling.

**Files:**
- `backend/app/application/services/knowledge_service.py`
- `backend/app/api/v1/knowledge.py`

**Tasks:**
1. Add PDF parsing with `pypdf` or `pdfplumber`: `ingest_pdf(file_bytes, source_title)`
2. Add URL crawling with `httpx` + `BeautifulSoup`: `ingest_url(url)` (fetch → strip HTML → chunk)
3. Support GitHub README + docs via raw GitHub URL
4. Add endpoint `POST /knowledge/ingest-url` with `{"url": "..."}`
5. Expose source type in `KnowledgeSourceSummary` (text / pdf / url)

---

#### Task 1.5 — Webhooks: Cover more events `[SHIPPED]`

> **Why it matters:** Use Case 2 (scheduled digest) and any production monitoring setup needs to react to failures and schedule fires, not just completions.

**Current state:** Only `execution_completed` and `campaign_completed` are delivered.

**Missing events in `infrastructure/webhooks/delivery.py`:**

```python
WEBHOOK_EVENTS = {
    "execution_completed",   # [SHIPPED]
    "campaign_completed",    # [SHIPPED]
    "execution_started",     # [SHIPPED]
    "execution_failed",      # [SHIPPED]
    "schedule_fired",        # [SHIPPED]
    "finetune_completed",    # [SHIPPED]
    "agent_updated",         # [SHIPPED]
}
```

**Tasks:**
1. Emit `execution_started` from `AgentService.execute()` right after DB creation
2. Emit `execution_failed` from `_run_background()` on exception
3. Emit `schedule_fired` from `schedule_worker_loop()`
4. Emit `finetune_completed` from the poll loop in `FinetuneService`
5. Emit `agent_updated` from `AgentService.update()`
6. Add per-event filtering in webhook config (`{"events": ["execution_completed"]}`)

---

**Sprint 1 unlocks:**
- Use Case 5 (fine-tune + deploy) becomes fully functional end-to-end
- Use Case 1 (RAG) works with PDFs and URLs, not just plain text
- Use Case 2 (scheduled digest) gets failure + start notifications
- Cursor/Claude agents can manage the full AgentForge workspace via MCP

---

### Sprint 2 — Memory and Builder (2 weeks)

**Goal:** Agents remember things across sessions. The builder becomes a first-class IDE.

---

#### Task 2.1 — Long-Term Agent Memory `[SHIPPED]`

> **Why it matters:** Every agent today forgets everything between sessions. A customer support agent can't remember that a user already reported a bug. A personal assistant can't learn your preferences. Memory is the difference between a demo and a product.

**Current state:** No memory implementation. The plan `docs/superpowers/plans/2026-04-04-long-term-memory.md` exists but hasn't started.

**Architecture:**

```python
# backend/app/domain/entities/memory.py
@dataclass
class MemoryEntry:
    id: UUID
    agent_id: UUID
    user_id: UUID
    thread_id: str | None
    content: str
    embedding: list[float]
    memory_type: str  # "episodic" | "semantic" | "procedural"
    importance: float  # 0.0–1.0
    created_at: datetime
    last_accessed_at: datetime
    access_count: int

# backend/app/domain/ports/memory_store.py
class MemoryStore(ABC):
    async def save(self, entry: MemoryEntry) -> None: ...
    async def recall(self, agent_id, user_id, query_embedding, top_k) -> list[MemoryEntry]: ...
    async def forget(self, entry_id: UUID) -> None: ...
    async def list_memories(self, agent_id, user_id) -> list[MemoryEntry]: ...
```

**Tasks:**
1. Create `backend/app/domain/entities/memory.py` and `backend/app/domain/ports/memory_store.py`
2. Create ORM `AgentMemoryModel` in `models.py` (pgvector for embedding)
3. Alembic migration: `agent_memories` table with HNSW index
4. Implement `PgvectorMemoryStore` in `infrastructure/memory/`
5. Add `memory_save` and `memory_recall` nodes to the LangGraph orchestrator
6. Add `"memory_save"` and `"memory_recall"` node types to the builder UI
7. API: `GET/DELETE /api/v1/agents/{id}/memories`

---

#### Task 3.1 — Node Inspector Panel (inline editing) `[SHIPPED]`

> **Why it matters:** Configuring nodes by clicking tiny embedded forms inside the canvas is cramped and error-prone. A dedicated side panel makes the builder feel like a real IDE.

**Current state:** Node config is embedded inline in each canvas node.

**Target:** A dedicated side panel that opens on node click, with type-specific forms, live Zod validation, and auto-save.

**Files:**
- `frontend/src/app/agents/[id]/builder/page.tsx` (modify)
- `frontend/src/components/builder/InspectorPanel.tsx` (create)
- `frontend/src/components/builder/forms/` (create: LLMNodeForm, ToolNodeForm, etc.)

**Tasks:**
1. Extract `useSelectedNode` hook (wraps React Flow `getNode`)
2. Create `InspectorPanel` component with dispatch on node type
3. Create one FormComponent per type: LLM, Tool, Conditional, Interrupt, Subagent, ASR, TTS
4. Live Zod validation with inline error messages
5. Auto-save with 500ms debounce → `PUT /api/v1/agents/{id}`
6. "Unsaved changes" indicator in the topbar

---

#### Task 3.2 — Missing nodes in the builder UI `[SHIPPED]`

> **Why it matters:** The backend supports Retrieval, Code execution, and Memory nodes — but the builder has no UI for them. Users have to hand-edit JSON to use these features.

**Tasks:**
1. Add **Retrieval** node (type `tool`, `tool_name: retrieve`, config: `top_k`)
2. Add **Code** node (type `tool`, `tool_name: python_repl`)
3. Add **Memory Save** / **Memory Recall** nodes (depends on Task 2.1)
4. Add config panel for Google Workspace nodes (read_gmail, create_calendar_event)

---

**Sprint 2 unlocks:**
- New use case: **Personal assistant that remembers** — agent recalls user preferences, past interactions, and learned facts across sessions
- New use case: **Code review agent** — Code node lets agents run Python to validate, lint, or test code snippets
- Builder becomes fast enough to use without frustration

---

### Sprint 3 — Analytics and Quality (1 week)

**Goal:** You can see what your agents are doing and trust the codebase.

---

#### Task 4.1 — Real-time metrics dashboard `[SHIPPED]`

> **Why it matters:** Right now `/dashboard` shows basic counts. You can't answer "which node is the bottleneck?" or "what did this agent cost last week?"

**New endpoints in `backend/app/api/v1/dashboard.py`:**

```python
GET /api/v1/dashboard/metrics?agent_id=&from=&to=&granularity=hour
# → { executions_by_hour, avg_latency_ms, p95_latency_ms, token_usage, estimated_cost_usd, error_rate }

GET /api/v1/dashboard/agents/{id}/timeline
# → time-series of executions + scores

GET /api/v1/dashboard/agents/{id}/node-perf
# → per-node latency over the last N executions
```

**Tasks:**
1. Add `execution_node_metrics` table (or enrich existing Langfuse spans)
2. Implement the 3 aggregation endpoints
3. Frontend `/analytics` page with Recharts: latency line charts, token bar charts, error heatmap
4. CSV export of metrics

---

#### Task 7.1 — Test coverage to 80% `[SHIPPED]`

> **Why it matters:** `backend/tests/unit/` was recently created. Without a coverage gate, regressions ship silently.

**Shipped:**
- `--cov-fail-under=80` already in `pyproject.toml` `addopts` (CI gate active)
- New unit tests: `tests/unit/test_domain_services.py` (44 tests — BudgetService, PiiMasker, cost_tracker, agent_diff)
- New unit tests: `tests/unit/test_domain_utils.py` (30 tests — coerce_message_content, validate_skill_source)
- New integration tests: `tests/api/test_new_endpoints.py` — dashboard metrics, PII masking, budget, export, workspace, memory
- 87 pure-Python unit tests pass with 0 external dependencies

---

#### Task 7.2 — Structured error handling `[SHIPPED]`

> **Why it matters:** Right now errors surface as raw Python exceptions or generic `HTTPException`. Frontend shows unhelpful messages. Debugging is painful.

**Tasks:**
1. Create `backend/app/domain/exceptions.py`: `DomainException`, `AgentNotFoundError`, `ExecutionFailedError`, `SkillValidationError`, etc.
2. Global FastAPI exception handler: `{"error": {"code": "AGENT_NOT_FOUND", "message": "...", "request_id": "..."}}`
3. Frontend: parse structured error codes → contextual toasts with suggested action

---

#### Task 3.3 — Undo/Redo + Keyboard Shortcuts + Auto-layout `[SHIPPED]`

**Tasks:**
1. Undo/redo with Zustand + graph state snapshots (`Ctrl+Z` / `Ctrl+Y`)
2. Auto-layout with `@dagrejs/dagre` (button "Arrange" or `Ctrl+Shift+L`)
3. Keyboard shortcuts: `Ctrl+S` save, `Ctrl+D` duplicate selected node, `Delete` remove node
4. Enable `<MiniMap>` React Flow (already available in the lib)

---

**Sprint 3 unlocks:**
- New use case: **Cost monitoring** — track token spend per agent per day, set budget alerts
- New use case: **Performance debugging** — identify which node in a graph is slow without reading logs

---

### Sprint 4 — Portability and Ecosystem (2 weeks)

**Goal:** Agents can live outside AgentForge. The SDK is complete. Everything is on PyPI.

---

#### Task 5.1 — Extended edge conditions and advanced routing `[SHIPPED]`

> **Why it matters:** Complex agents need routing logic beyond "does the output contain this string?" Scoring thresholds, numeric comparisons, and compound conditions are required for production-grade decision trees.

**Current state:** `conditional` node supports only: `always`, `contains`, `regex`, `json_path`.

**New operators in `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`:**

```python
OPERATORS = {
    "contains": ...,     # [SHIPPED]
    "regex": ...,        # [SHIPPED]
    "json_path": ...,    # [SHIPPED]
    "always": ...,       # [SHIPPED]
    "equals": ...,       # [PLANNED]
    "gt": ...,           # [PLANNED] (score > threshold)
    "lt": ...,           # [PLANNED]
    "not_contains": ..., # [PLANNED]
    "and": ...,          # [PLANNED] (compound conditions)
    "or": ...,           # [PLANNED]
}
```

**Tasks:**
1. Extend `EdgeCondition` in `backend/app/domain/graph_definition.py`
2. Implement new operators in the orchestrator
3. Add `EdgeRuleBuilder` component in the builder UI (visual rule builder)
4. Add "test condition" mode: paste example input → see which branch would be taken

---

#### Task 6.1 — AFG v2 and multi-format export `[SHIPPED]`

> **Why it matters:** AgentForge agents should be portable. A team should be able to export an agent, run it in their own infra, and not depend on the AgentForge server.

**Current state:** Export/import works in internal JSON format only.

**Target:**

```bash
# CLI
agentforge export agent-id --format python    # → agent_standalone.py
agentforge export agent-id --format docker    # → Dockerfile + agent.py
agentforge export agent-id --format langgraph # → langgraph_config.json

# API
POST /api/v1/agents/{id}/export?format=python
POST /api/v1/agents/{id}/export?format=docker
POST /api/v1/agents/{id}/export?format=langgraph
```

**Tasks:**
1. Create `backend/app/application/export_service.py` with 3 formats
2. Create `sdk/agentforge/exporters/python_exporter.py` → self-contained standalone script
3. Create `sdk/agentforge/exporters/docker_exporter.py` → minimal Dockerfile
4. Add corresponding API endpoints
5. Add "Export as Python / Docker" buttons on the agent detail page

---

#### Task 6.2 — Standalone Runtime (without FastAPI) `[SHIPPED]`

> **Why it matters:** After exporting an agent, you need to run it somewhere. `agentforge serve` turns any exported agent into a local HTTP server in one command.

**Target:**

```bash
agentforge serve agent.afg.yaml --port 8080
# → exposes POST /execute and GET /stream/:id
```

**Tasks:**
1. Create `sdk/agentforge/runtime/server.py` (minimal FastAPI: 3 routes)
2. Create `sdk/agentforge/runtime/loader.py` (loads `.afg.yaml` → `LocalAgent`)
3. Wire into existing CLI: `agentforge serve <file>`
4. Test: export agent → `agentforge serve` → curl execute

---

#### Task 8.3 — Publish SDKs to PyPI and npm `[SHIPPED]`

> **Why it matters:** Right now you have to clone the repo to use the SDKs. PyPI + npm publication makes AgentForge a real developer platform.

**Shipped:**

- `sdk-client/` builds cleanly: `uv build` → `dist/agentforge_client-0.1.0-py3-none-any.whl` + sdist
- `sdk-js/` builds cleanly: `tsc` → `dist/` with type declarations
- `.github/workflows/publish-sdks.yml` — triggered on GitHub Release (or `workflow_dispatch`):
  - **Python**: OIDC trusted publishing to PyPI (no secret needed — configure at pypi.org/manage/project/agentforge-client/settings/publishing/)
  - **npm**: `npm publish --provenance --access public` using `NPM_TOKEN` secret
- To publish: create a GitHub Release tagged `v0.1.0` and the workflow fires automatically

---

**Sprint 4 unlocks:**
- New use case: **Self-hosted agent** — export any agent, run it with `agentforge serve`, no AgentForge server needed
- New use case: **CI/CD pipeline agent** — `pip install agentforge-client` in a GitHub Action, trigger agents from any workflow
- New use case: **Complex routing** — agent scores a response 0–10 and routes to different handlers based on score threshold

---

### Sprint 5 — Hub and Triggers (1 week)

**Goal:** Agents can be shared and triggered from external systems.

---

#### Task 8.1 — AgentForge Hub (internal marketplace) `[SHIPPED]`

> **Why it matters:** Teams build great agents and then can't share them. A hub lets you publish, discover, and clone agents — turning individual work into team assets.

**Current state:** Agents have `is_public: bool` in the entity but no public listing endpoint.

**Tasks:**
1. Add `stars: int` to the `agents` table
2. Create `GET /api/v1/hub/agents` (public agents, paginated, filtered by category)
3. Create `POST /api/v1/hub/agents/{id}/clone`
4. Create frontend `/hub` page with grid + category filters
5. Add "Publish to Hub" button on the agent detail page

---

#### Task 8.2 — Inbound Webhook Triggers `[SHIPPED]`

> **Why it matters:** Right now agents can only be triggered by API calls or schedules. Inbound webhooks let any external system (GitHub, Slack, Stripe, Zapier) trigger an agent directly.

**Current state:** `WebhookSubscription` ORM and table exist for outbound delivery. Inbound triggers are missing.

**Tasks:**
1. Create `POST /api/v1/agents/{id}/webhook/:secret` — receives external payload → triggers agent
2. Generate a secret per agent at creation (`secrets.token_urlsafe(32)`)
3. Show "Copy webhook URL" with secret in the builder UI

---

#### Task 7.3 — Voice Sample Storage: Move to S3 `[SHIPPED]`

> **Why it matters:** Storing audio as base64 in PostgreSQL is a known scaling bottleneck. The code already has a comment flagging this.

**Current state:** `voice_sample_repo.py` stores audio as base64 in PostgreSQL.

**Tasks:**
1. Add `S3_BUCKET` and `S3_ENDPOINT_URL` to `.env` / `config.py`
2. Create `infrastructure/storage/s3_store.py` with `upload_audio(bytes) → url`
3. Update `voice_sample_repo.py` to store S3 URL instead of base64
4. Alembic migration: `audio_data TEXT → audio_url TEXT`

---

**Sprint 5 unlocks:**
- New use case: **GitHub-triggered code review agent** — push to a repo → GitHub webhook → AgentForge agent reviews the diff → posts a comment
- New use case: **Slack bot agent** — Slack sends a message event → inbound webhook → agent responds
- New use case: **Browse and clone community agents** — find a pre-built customer support agent, clone it, customize it

---

### Sprint 6 — Frontend Design & UX Polish ✅ `[SHIPPED]`

**Goal:** AgentForge goes from "functional dark app" to "product people want to show off." Every surface gets intentional design treatment — typography, spatial rhythm, motion, empty states, and onboarding.

> **Design direction:** Refined dark-premium. The aurora mesh and violet/teal palette are the right foundation — the work is sharpening contrast, adding spatial hierarchy, and making interactions feel alive without being noisy. Think Linear meets Vercel dashboard: dense but breathable, every element earns its place.

---

#### Task 9.1 — Typography System: Sans-Serif Body + Mono Accents `[SHIPPED]`

> **Why it matters:** The app currently uses `font-mono` as the default body font across all UI text. Mono is great for code and IDs — it's wrong for paragraphs, labels, and navigation. This single change makes the whole app feel more polished and readable.

**Current state:** `globals.css` sets `body { font-mono }`. Space Grotesk is loaded but underused.

**Design target:**
- Body / UI labels / navigation → `font-sans` (Space Grotesk or swap to a more distinctive pairing)
- Code blocks, execution IDs, node labels, JSON → `font-mono` via `.af-mono` utility class
- Display headings (dashboard title, empty states, onboarding) → consider a heavier weight or a contrasting serif/display face for personality

**Files:**
- `frontend/src/app/globals.css` — `@layer base body`, add `.af-mono` utility
- `frontend/src/components/layout/ToolShell.tsx` — nav labels
- `frontend/src/app/chat/page.tsx`, `ChatSlideOver.tsx` — message bubbles
- `frontend/src/app/dashboard/page.tsx` — stat labels, headings

**Tasks:**
1. In `globals.css` `@layer base`, switch `body` from `font-mono` to `font-sans`
2. Add `.af-mono` utility class for technical strings (IDs, code, logs)
3. Audit every page: replace raw `font-mono` class with `.af-mono` where appropriate
4. Increase `--color-af-muted` contrast slightly (`#8888aa` → `#9b9bb8`) for WCAG AA on dark bg
5. Add `leading-relaxed` to message bubble text in chat surfaces
6. Commit: `style(frontend): switch to sans-serif body, add af-mono utility`

---

#### Task 9.2 — Aurora Background: Sharper, Less Muddy `[SHIPPED]`

> **Why it matters:** The current aurora mesh blends three gradients at similar opacity/intensity, creating a grey-brown muddy background on some screens. The fix is separating the planes: one dominant cool gradient, two subtle accent gradients, lower overall opacity.

**Current state:** `AuroraBackground.tsx` renders 3 blobs + mesh. The mesh `hue-rotate` animation drifts into greens and greys.

**Design target:** Clean dark background with a single strong violet bloom at top-center, two whisper-level teal/indigo accents. Blobs more diffuse (higher blur, lower opacity). Animation subtle enough to not distract during work sessions.

**Files:**
- `frontend/src/app/globals.css` — `.af-aurora-mesh` radial gradients, `@keyframes af-aurora-mesh-shift`
- `frontend/src/components/layout/AuroraBackground.tsx` — blob opacity values

**Tasks:**
1. Replace `.af-aurora-mesh` background with separated planes:
```css
.af-aurora-mesh {
  background:
    radial-gradient(ellipse 75% 45% at 50% -15%, rgba(79, 70, 229, 0.14), transparent 58%),
    radial-gradient(ellipse 55% 38% at 95% 45%, rgba(124, 58, 237, 0.09), transparent 52%),
    radial-gradient(ellipse 45% 32% at 5% 85%, rgba(45, 212, 191, 0.07), transparent 48%);
}
```
2. Reduce `hue-rotate` max in `@keyframes af-aurora-mesh-shift`: `22deg` → `10deg`
3. Lower blob opacities in `AuroraBackground.tsx`: `0.16 → 0.10`, `0.11 → 0.07`, `0.12 → 0.08`
4. Verify `@media (prefers-reduced-motion: reduce)` still freezes all animation
5. Commit: `style(frontend): soften aurora mesh, reduce hue drift`

---

#### Task 9.3 — Motion System: Unified Tokens + Purposeful Transitions `[SHIPPED]`

> **Why it matters:** Panels, drawers, modals, and cards all use different durations (`200ms`, `300ms`, `500ms`) and easing curves. The result feels inconsistent — some things snap, some things drag. A shared motion token system makes the whole app feel coherent.

**Design target:** Two motion speeds — `enter` (280ms, spring-like ease-out) for panels/drawers, `standard` (200ms, ease) for hover states and micro-interactions. No `transition-all` on heavy elements.

**Files:**
- `frontend/src/app/globals.css` — add CSS custom properties + `.af-panel-enter` utility
- `frontend/src/components/chat/ChatSlideOver.tsx`
- `frontend/src/components/chat/FloatingChatButton.tsx`
- `frontend/src/app/dashboard/page.tsx`, `frontend/src/app/agents/page.tsx`

**Tasks:**
1. Add motion tokens to `globals.css`:
```css
:root {
  --af-motion-enter: 280ms cubic-bezier(0.22, 1, 0.36, 1);
  --af-motion-standard: 200ms ease;
  --af-motion-exit: 200ms cubic-bezier(0.4, 0, 1, 1);
}
```
2. Add `.af-panel-enter` utility: `translate-y-2 opacity-0 → translate-y-0 opacity-100` with `var(--af-motion-enter)`
3. Replace scattered duration values in `ChatSlideOver`, `FloatingChatButton`, and drawer components
4. Remove `transition-all` from any element with `transform` or `box-shadow` (use explicit properties)
5. Commit: `style(frontend): unify motion tokens across shell and chat`

---

#### Task 9.4 — Empty States: Purposeful, Not Blank `[SHIPPED]`

> **Why it matters:** Every page that can be empty (`/agents`, `/knowledge`, `/campaigns`, `/executions`, `/finetune`) currently shows either nothing or a generic message. Empty states are the highest-leverage onboarding surface — they tell users exactly what to do next.

**Design target:** Each empty state has: a distinctive illustration or icon (SVG, not emoji), a one-line explanation of what this section does, and a single primary CTA that creates the first item.

**Files:**
- `frontend/src/components/ui/EmptyState.tsx` (create — shared component)
- `frontend/src/app/agents/page.tsx`
- `frontend/src/app/knowledge/page.tsx`
- `frontend/src/app/campaigns/page.tsx`
- `frontend/src/app/executions/page.tsx`
- `frontend/src/app/finetune/page.tsx`

**Tasks:**
1. Create `EmptyState` component:
```tsx
// frontend/src/components/ui/EmptyState.tsx
interface EmptyStateProps {
  icon: React.ReactNode        // SVG illustration
  title: string
  description: string
  action?: { label: string; href: string }
}
```
2. Design 5 distinct SVG illustrations (inline, themed with `--color-af-primary` stroke)
3. Wire `EmptyState` into each page with page-specific copy and CTA
4. Add subtle entrance animation: `af-motion-fade-in` (already in `globals.css`)
5. Commit: `feat(frontend): add purposeful empty states across all main pages`

---

#### Task 9.5 — Dashboard: From Counts to Insights `[SHIPPED]`

> **Why it matters:** The current dashboard shows static count cards. A good dashboard answers "what happened recently?" and "do I need to act on anything?" without clicking into sub-pages.

**Design target:** Three zones:
1. **Activity feed** — last 5 executions with status badge, agent name, duration, and quick link
2. **Health at a glance** — 3 stat cards: total executions (7d), avg latency, error rate — with subtle sparkline
3. **Quick actions** — "New Agent", "Run Campaign", "Open Forge" — prominent, not buried

**Files:**
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/components/dashboard/ActivityFeed.tsx` (create)
- `frontend/src/components/dashboard/StatCard.tsx` (create — with sparkline via Recharts `<Sparkline>`)
- `frontend/src/components/dashboard/QuickActions.tsx` (create)

**Tasks:**
1. Create `ActivityFeed` component — calls `GET /api/v1/executions?limit=5` on mount
2. Create `StatCard` with optional Recharts `<LineChart>` sparkline (7-day trend)
3. Create `QuickActions` with 3 primary action buttons (gradient border on hover)
4. Redesign dashboard layout: 3-col grid on desktop, stacked on mobile
5. Add skeleton loaders (Tailwind `animate-pulse`) while data loads
6. Commit: `feat(frontend): redesign dashboard with activity feed and quick actions`

---

#### Task 9.6 — Agent Builder: Visual Hierarchy and Node Aesthetics `[SHIPPED]`

> **Why it matters:** The React Flow canvas is functional but visually flat — all nodes look similar, making it hard to read a complex graph at a glance. Visual differentiation by node type makes graphs self-documenting.

**Design target:**
- Each node type has a distinct color accent on its left border (LLM → violet, Tool → blue, Conditional → amber, Interrupt → red, ASR/TTS → teal, Subagent → emerald)
- Node header shows type icon + type label in small caps
- Selected node gets a glow ring (`box-shadow: 0 0 0 2px var(--color-af-primary)`)
- Edge labels styled as small pills, not raw text
- Canvas background: subtle dot grid (React Flow `<Background variant="dots">`) instead of solid dark

**Files:**
- `frontend/src/components/builder/` — node components (LLMNode, ToolNode, etc.)
- `frontend/src/app/agents/[id]/builder/page.tsx`
- `frontend/src/app/globals.css` — node color tokens

**Tasks:**
1. Add node color tokens to `globals.css`:
```css
:root {
  --af-node-llm:         #7c3aed;  /* violet */
  --af-node-tool:        #2563eb;  /* blue */
  --af-node-conditional: #d97706;  /* amber */
  --af-node-interrupt:   #dc2626;  /* red */
  --af-node-speech:      #0d9488;  /* teal */
  --af-node-subagent:    #059669;  /* emerald */
  --af-node-memory:      #9333ea;  /* purple */
}
```
2. Add left-border color accent to each node component via `border-l-4` + node-type token
3. Add type icon (SVG or Lucide) to node header
4. Add `box-shadow` glow on `selected` state (React Flow `selected` prop)
5. Switch canvas `<Background>` to `variant="dots"` with low-opacity dots
6. Style edge labels as `<span>` pills with `bg-af-surface/80 text-xs px-1.5 py-0.5 rounded`
7. Commit: `style(builder): add node type color system and visual hierarchy`

---

#### Task 9.7 — Forge UI: Chat Bubble Polish + Composer UX `[SHIPPED]`

> **Why it matters:** Forge is the primary daily-use surface. The chat bubbles and composer are where users spend most of their time. Small improvements here have outsized impact on perceived quality.

**Design target:**
- User bubbles: right-aligned, violet-tinted background (`bg-af-primary/15`), rounded-br-sm for "tail" effect
- Assistant bubbles: left-aligned, subtle surface card (`bg-af-surface`), slightly wider max-width
- Composer: auto-resize textarea (no fixed height), `Shift+Enter` for newline, `Enter` to send, character count near limit
- Typing indicator: 3-dot pulse animation while streaming (replaces or supplements existing toasts)
- Tab bar: active tab gets underline accent, not just background change — cleaner visual indicator

**Files:**
- `frontend/src/app/forge/page.tsx`
- `frontend/src/components/chat/ChatUI.tsx`
- `frontend/src/components/chat/ChatSlideOver.tsx`

**Tasks:**
1. Restyle user/assistant bubbles with distinct backgrounds and alignment
2. Replace fixed-height textarea with `useAutoResize` hook (adjusts `rows` on input)
3. Add `Shift+Enter` / `Enter` keyboard handling to composer
4. Add 3-dot typing indicator component shown while `isStreaming === true`
5. Restyle tab bar: `border-b-2 border-af-primary` on active tab instead of background fill
6. Commit: `style(forge): polish chat bubbles, composer UX, and tab indicator`

---

#### Task 9.8 — Onboarding Flow: First-Run Experience `[SHIPPED]`

> **Why it matters:** A new user landing on the dashboard with no agents sees an empty screen with no guidance. The first 5 minutes determine whether someone becomes a regular user. A lightweight onboarding checklist (not a modal wizard) keeps users oriented without being annoying.

**Design target:** A dismissible "Getting started" card on the dashboard (shown only when `agents.length === 0 && executions.length === 0`). 4 steps with checkmarks as they're completed:

```
□ Create your first agent
□ Add a skill or knowledge base
□ Run your first execution
□ Try Forge
```

No modal. No forced flow. Just a persistent card that tracks progress and disappears when all 4 are done.

**Files:**
- `frontend/src/components/dashboard/OnboardingChecklist.tsx` (create)
- `frontend/src/app/dashboard/page.tsx` (add checklist)
- `frontend/src/lib/onboarding.ts` (create — localStorage state for checklist progress)

**Tasks:**
1. Create `onboarding.ts` with `getOnboardingState()` / `markStep(step)` / `isDismissed()` using `localStorage`
2. Create `OnboardingChecklist` card component — 4 steps, each with a link to the relevant page
3. Auto-mark steps complete: check `agents.length > 0`, `executions.length > 0`, etc. on mount
4. Add dismiss button (stores `dismissed: true` in localStorage)
5. Wire into dashboard — show above activity feed when not dismissed and not all steps complete
6. Commit: `feat(frontend): add first-run onboarding checklist to dashboard`

---

**Sprint 6 unlocks:**
- The app feels like a product, not a prototype — every surface has intentional design
- New users understand what to do within 30 seconds (onboarding checklist)
- The builder is readable at a glance — graph topology communicates agent logic visually
- Forge becomes the daily driver it's meant to be — chat UX matches user expectations
- Empty states turn dead ends into conversion moments

---

---

### Sprint 7 — Live Execution & Command Palette (1 week)

**Goal:** The app feels truly alive. You can see agents think in real time, and navigate the whole product from the keyboard.

> **Design direction:** This sprint is about making the invisible visible. When an agent executes, every node in the canvas should light up. Navigation should feel instant. The product goes from "functional" to "alive."

---

#### Task 10.1 — Live Node Execution Overlay in Builder `[SHIPPED]`

> **Why it matters:** Right now the builder is static — you hit "Run" and switch to the executions page to see results. The canvas should animate in real time: which node is running, which edges are being traversed, where it's stuck.

**Design target:**
- Active node gets a pulsing violet glow ring (`box-shadow: 0 0 0 3px var(--af-node-llm)`) + spinning ring border
- Traversed edges animate a "flow particle" moving along the edge path (SVG `stroke-dashoffset` animation)
- Completed nodes get a green checkmark badge overlay
- Failed nodes get a red error badge with shake micro-animation
- Status bar at the bottom of the canvas: `Running · Node 2/4 · LLM ·  1.2s`

**Files:**
- `frontend/src/app/agents/[id]/builder/page.tsx` — add execution SSE subscription
- `frontend/src/components/builder/ExecutionOverlay.tsx` (create)
- `frontend/src/app/globals.css` — `@keyframes af-node-pulse`, `@keyframes af-edge-flow`

**Tasks:**
1. Subscribe to `GET /api/v1/agents/{id}/executions/{exec_id}/stream` SSE from the builder page
2. Map `node_started` / `node_completed` / `node_failed` events to canvas node state
3. Create `ExecutionOverlay` — wraps React Flow, overlays state badges on top of nodes
4. Add `@keyframes af-node-pulse` (ring that breathes outward) to `globals.css`
5. Animate edge traversal with SVG `stroke-dashoffset` flow particle along active edges
6. Add status bar component at bottom of canvas with node counter + elapsed time

---

#### Task 10.2 — Global Command Palette (Cmd+K) `[SHIPPED]`

> **Why it matters:** Power users navigate via keyboard. A command palette turns the entire app surface into a single searchable interface — no more hunting through the nav.

**Design target:** Full-screen overlay backdrop, centered floating search box. Results grouped by type: Pages, Agents, Actions, Recent. Animated entrance (scale from 0.95 + fade). Arrow keys navigate. Enter executes.

**Files:**
- `frontend/src/components/ui/CommandPalette.tsx` (create)
- `frontend/src/components/layout/ClientProviders.tsx` — register `Cmd+K` keybinding
- `frontend/src/app/globals.css` — `@keyframes af-palette-in`

**Commands to support:**
```
> Go to Dashboard / Agents / Forge / Knowledge / …   (navigation)
> New Agent / New Campaign / Open Forge               (actions)
> Search agents: "customer support"                   (fuzzy search via API)
> Run agent: {agent-name}                             (direct execute modal)
> Toggle light / dark mode                            (settings)
```

**Tasks:**
1. Create `CommandPalette` with `cmdk` library (or hand-rolled with `fuse.js` fuzzy search)
2. Register global `Cmd+K` / `Ctrl+K` listener in `ClientProviders`
3. Populate static commands (navigation + actions) + dynamic results from `GET /api/v1/agents?q=`
4. Animate palette: `@keyframes af-palette-in { from { opacity:0; scale:0.95; } to { opacity:1; scale:1; } }`
5. Add backdrop blur overlay (`backdrop-blur-sm bg-black/40`)
6. Keyboard navigation: `ArrowUp/Down`, `Enter` to execute, `Esc` to dismiss

---

#### Task 10.3 — Notification Center (SSE-driven) `[SHIPPED]`

> **Why it matters:** Right now feedback from background operations (schedule fires, campaign completion, fine-tune done) only appears if you're on the right page. A persistent notification center surfaces these events system-wide.

**Design target:** Bell icon in the header with unread badge count. Click opens a slide-down panel listing the last 20 notifications. Each notification is typed: `execution_completed` → green, `execution_failed` → red, `campaign_completed` → violet, `finetune_completed` → teal. "Mark all read" button. Notifications persist in `localStorage`.

**Files:**
- `frontend/src/components/layout/NotificationCenter.tsx` (create)
- `frontend/src/components/layout/AppHeader.tsx` — add bell icon
- `frontend/src/hooks/useNotifications.ts` (create)

**Tasks:**
1. Create `useNotifications` hook — subscribes to a new `GET /api/v1/notifications/stream` SSE endpoint (or reuses webhook event stream)
2. Add backend `GET /api/v1/notifications` endpoint — queries recent webhook deliveries + execution events for the user
3. Store notifications in `localStorage` with `read: boolean` state
4. Create `NotificationCenter` panel — slide-down from header, `af-panel-enter` motion
5. Badge on bell icon with count of unread — red dot when > 0
6. Mark individual or all-read action

---

#### Task 10.4 — Staggered List Animations + Page Enter Transitions `[SHIPPED]`

> **Why it matters:** Currently every page loads its content all at once. Staggered entrance animations make the UI feel responsive and premium — each card cascades in, giving the eye a natural sequence to follow.

**Design target:**
- Agent cards on `/agents` page: cascade in from bottom with 40ms delay between items
- Execution rows in the list: same cascade pattern
- Page transitions: brief opacity + translate-Y fade on route changes

**Files:**
- `frontend/src/app/globals.css` — `@keyframes af-stagger-in`, `.af-stagger-item`
- `frontend/src/components/ui/StaggeredList.tsx` (create — wrapper component)
- `frontend/src/app/agents/page.tsx`, `frontend/src/app/executions/page.tsx`

**Tasks:**
1. Add `@keyframes af-stagger-in` to `globals.css`:
```css
@keyframes af-stagger-in {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.af-stagger-item {
  animation: af-stagger-in 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
}
```
2. Create `StaggeredList` wrapper that clones children and applies `animation-delay: calc(var(--index) * 40ms)` via CSS custom property
3. Apply to agent cards, execution rows, knowledge sources, campaign cards
4. Add page-level fade-in: wrap route content in a `div` with `af-motion-fade-in` that re-mounts on navigation

---

**Sprint 7 unlocks:**
- Builder becomes a live execution monitor — no need to leave the canvas
- Power users navigate 3× faster with Cmd+K
- Background operations are no longer silent — the notification center surfaces everything
- The app feels alive and responsive, not static

---

### Sprint 8 — Collaboration & Teams (2 weeks)

**Goal:** Multiple people can work in the same workspace. Agents are shared assets, not personal files.

---

#### Task 11.1 — User Roles & Workspace Permissions `[SHIPPED]`

> **Why it matters:** Right now every user in AgentForge has full access to everything. Teams need to control who can edit agents, who can run campaigns, and who can change settings.

**Roles (per workspace):**
```
owner   → all permissions
editor  → create/edit agents, run campaigns, view all
viewer  → read-only: view agents, view executions, can't modify
```

**Tasks:**
1. Add `workspace_members` table: `workspace_id, user_id, role`
2. FastAPI dependency `require_role(min_role: str)` — inject on protected routes
3. Settings page `/settings/team` — invite by email, assign role, remove member
4. Frontend: hide/disable edit controls for `viewer` role (read from JWT claim or API)

---

#### Task 11.2 — Agent Sharing with Link `[SHIPPED]`

> **Why it matters:** "I want to share this agent with a colleague" currently requires giving them full account access. Link sharing with configurable permissions is a fundamental collaboration primitive.

**Tasks:**
1. Add `share_tokens` table: `token, agent_id, permission (view|execute), expires_at`
2. `POST /api/v1/agents/{id}/share` → returns share URL
3. `GET /api/v1/shared/{token}` → returns agent definition (no auth required for `view`)
4. `POST /api/v1/shared/{token}/execute` → executes agent (no auth required for `execute`)
5. "Share" button on agent detail page with copy-to-clipboard and expiry picker

---

#### Task 11.3 — Real-Time Collaborative Builder `[SHIPPED]`

> **Why it matters:** Two engineers iterating on the same agent graph currently conflict — last save wins. Real-time presence and conflict detection prevents data loss.

**Target:** Presence cursors (colored dot + username) on the canvas. Optimistic locking on node edits — if two users edit the same node, one gets a "conflict" warning and can merge or discard.

**Stack:** Use WebSockets (`GET /api/v1/agents/{id}/collaborate/ws`) + yjs CRDT for graph state, or simpler: cursor broadcast only + last-write-wins with server-side timestamp conflict detection.

**Tasks:**
1. WebSocket endpoint for agent collaboration channel
2. Broadcast cursor positions (user, x, y on canvas) to all connected clients
3. Render remote cursors as colored floating labels on the React Flow canvas
4. Add server-side optimistic locking: reject updates older than the current `updated_at`
5. Frontend conflict toast: "Nicolas saved a conflicting version — [View diff] [Override]"

---

#### Task 11.4 — Audit Log `[SHIPPED]`

> **Why it matters:** Enterprise teams need to know who did what. "Who deleted that campaign?" should be answerable.

**Tasks:**
1. `audit_log` table: `event_type, user_id, resource_type, resource_id, payload, created_at`
2. Log all write operations across services (agents, campaigns, knowledge, webhooks)
3. `GET /api/v1/audit?resource_type=&user_id=&from=&to=` — paginated log
4. Frontend `/settings/audit` page — table with filter controls

---

**Sprint 8 unlocks:**
- Teams can work on shared agents without stepping on each other
- Agents become shareable links, not just internal tools
- You can audit every change — required for compliance-conscious teams

---

### Sprint 9 — AI-Native: Auto-Optimize & Self-Improve (2 weeks)

**Goal:** The AI helps you build better agents. AgentForge uses its own LLM capabilities to analyze, suggest, and improve your agents automatically.

---

#### Task 12.1 — Forge "Design Mode": Natural Language → Graph `[SHIPPED]`

> **Why it matters:** Most users don't know which nodes to combine to solve their problem. If you can describe what you want ("An agent that reads emails, classifies them, and replies to urgent ones"), Forge should draft the graph for you.

**Implementation:** Use the existing `POST /api/v1/generation/generate_agent` endpoint (already exists in `generation_service.py`) — expose it as a Forge mode.

**Tasks:**
1. Add "Design" tab to the Forge composer alongside existing tool tabs
2. System prompt: structured agent graph generator with JSON schema output
3. On response: parse graph JSON → call `POST /api/v1/agents` → redirect to builder
4. Show a preview card of the generated graph structure before creating it
5. "Refine" flow: user can follow up in the same conversation to adjust the graph

---

#### Task 12.2 — Automatic Prompt Optimizer `[SHIPPED]`

> **Why it matters:** System prompts are the highest-leverage variable in agent quality, but iterating on them manually is slow. An automatic optimizer runs A/B variants against your test cases and shows you which prompt wins.

**Architecture:**
```
User selects: base prompt + test inputs (from flagged executions)
System generates: 3 prompt variants via LLM
System runs: each variant against all test inputs
System scores: output quality via LLM judge (rubric: accuracy, tone, safety)
System reports: variant comparison table with winner highlighted
```

**Tasks:**
1. New entity `PromptExperiment` with variants and scores
2. `POST /api/v1/agents/{id}/optimize-prompt` — triggers background experiment
3. Frontend: "Optimize Prompt" button on LLM node inspector panel
4. Results panel: side-by-side prompt variants with score bars + diff highlight

---

#### Task 12.3 — Agent Health Score `[SHIPPED]`

> **Why it matters:** "Is my agent production-ready?" should have a single, clear answer — not require checking 5 different pages.

**Composite score (0–100):**
```
Security score    (from campaigns)   → 30%
Error rate        (last 7d)          → 25%
Latency p95       (vs baseline)      → 20%
Coverage          (test cases exist) → 15%
Memory leakage    (context window %) → 10%
```

**Tasks:**
1. Compute score in `AgentService` — query campaign results, execution stats, test coverage
2. Store in `agents.health_score` column
3. Show health badge on agent cards and detail page (green/yellow/red ring)
4. Dashboard: list agents sorted by health score, surface the ones that need attention

---

#### Task 12.4 — AI-Suggested Node Connections in Builder `[SHIPPED]`

> **Why it matters:** Users often don't know what to connect after adding a node. If the builder can suggest likely next nodes based on the current graph structure and common patterns, agent design becomes faster.

**Target:** After adding a node, a small "Suggest next" chip appears. Click it → a dropdown shows 2–3 suggestions: "Add LLM → END", "Add Conditional → branch", etc. — derived from the most common graph patterns in the dataset.

**Tasks:**
1. Collect graph topology statistics from existing agent definitions (in-memory, no external call)
2. `POST /api/v1/generation/suggest-next-node` — takes current graph JSON → returns suggestions
3. Builder: "Suggest →" chip on the active node's output handle
4. Animate suggestion dropdown with `af-motion-enter` token

---

**Sprint 9 unlocks:**
- Non-technical users can create agents from a description — no node wiring required
- System prompts improve automatically — quality goes up without manual iteration
- A single health score replaces manually checking security, errors, and latency separately
- The builder guides users toward valid graphs — fewer broken agents

---

### Sprint 10 — Enterprise & Production Hardening (2 weeks)

**Goal:** AgentForge is ready for teams that have compliance, security, and scale requirements.

---

#### Task 13.1 — SSO: SAML 2.0 / OIDC `[SHIPPED]`

> **Why it matters:** Enterprise teams use centralized identity (Okta, Azure AD, Google Workspace). SSO is a hard requirement for enterprise sales, not a nice-to-have.

**Tasks:**
1. Add `python-saml` (SAML) + `python-jose` (OIDC) dependencies
2. Config: `SSO_PROVIDER`, `SSO_METADATA_URL`, `SSO_CLIENT_ID/SECRET`
3. `GET /api/v1/auth/sso/login` → redirect to IdP
4. `POST /api/v1/auth/sso/callback` → validate assertion → issue JWT
5. Settings page: `/settings/sso` — configure provider, test connection

---

#### Task 13.2 — PII Masking in Execution Traces `[SHIPPED]`

> **Why it matters:** Execution traces may contain user-provided input with PII. Teams in regulated industries (healthcare, finance) cannot store raw PII in logs.

**Tasks:**
1. Add `pii_masking: bool` flag to agent config
2. On `execution_completed`: run output through `presidio-analyzer` → replace PII with `[MASKED]`
3. Apply masking before writing to `execution_outputs` table and before webhook delivery
4. Settings: per-agent PII masking toggle + custom entity types (e.g., `ACCOUNT_NUMBER`)

---

#### Task 13.3 — Cost Budgets and Alerts `[SHIPPED]`

> **Why it matters:** A misconfigured agent running on a schedule can burn through API budget in hours. Budgets + alerts prevent surprise bills.

**Tasks:**
1. `budget_rules` table: `agent_id | workspace_id, period (day|month), max_cost_usd, alert_threshold_pct`
2. Check budget in `CostMeter` after each execution — block further executions if over limit
3. Alert at threshold (e.g., 80% of budget): emit `budget_warning` webhook event
4. Frontend: budget configuration on agent settings + budget usage bar on dashboard

---

#### Task 13.4 — Rate Limiting per Team `[SHIPPED]`

> **Why it matters:** Multi-tenant deployments need to prevent one team from starving others.

**Tasks:**
1. Add Redis-based rate limiter middleware (using `slowapi`)
2. Limits: `executions/minute`, `api_calls/minute`, `tokens/day` — configurable per workspace tier
3. `429 Too Many Requests` response with `Retry-After` header
4. Admin panel: `/admin/rate-limits` — view current usage per workspace

---

**Sprint 10 unlocks:**
- Enterprise customers can deploy AgentForge behind their own IdP
- Compliance teams can enable PII masking — no raw user data in traces
- Finance teams can set hard caps on agent spend
- Multi-tenant deployments are fair and safe

---

## Frontend & Animation Improvement Proposals

> These proposals go beyond the shipped Sprint 6 polish. Each is a concrete, implementable improvement with design rationale and technical approach.

---

### Proposal A — Execution Flow Particle Animation (Builder Canvas)

**Problem:** The builder canvas is purely static. You run an agent and get no visual feedback of traversal.

**Design:** When an execution is live, small luminous particles travel along each active edge, moving from source to target node. The particle is a 4px dot in the source node's accent color, animated with `stroke-dashoffset` on the SVG path. The active node's border becomes an animated dashed ring (like a marching ants selection).

```css
@keyframes af-edge-flow {
  from { stroke-dashoffset: 24; }
  to   { stroke-dashoffset: 0; }
}
/* Applied to <path> of active edges via React Flow custom edge component */
```

**Effort:** Medium — requires a custom React Flow edge component and SSE-to-canvas state bridge.

---

### Proposal B — Command Palette with Animated Result Groups

**Problem:** Navigating to a specific agent requires: sidebar click → wait for list load → find agent → click.

**Design:** `Cmd+K` opens a centered floating palette with spring entrance (`scale(0.95) → scale(1)` in 180ms). Results appear in typed groups: **Pages** (instant), **Recent Agents** (from localStorage), **Search** (debounced API call). Each group header has a subtle top border + uppercase kicker label. Selected item gets a violet glow background.

**Effort:** Low–Medium — `cmdk` library or equivalent handles keyboard behavior. Main work is the API integration and design.

---

### Proposal C — Morphing Score Ring on Campaigns Page

**Problem:** The `ScoreRing` component is a static SVG. It renders the final score with no animation.

**Design:** On mount, the ring animates from `stroke-dashoffset: 100%` to the target percentage over 800ms with a spring easing. The score counter inside counts up from 0 to the target number. Color transitions from gray → red → amber → green as it fills, reflecting the score tier.

```tsx
// Animate dashoffset from circumference → (1 - score/100) * circumference
// Use CSS @keyframes af-ring-fill or animate via requestAnimationFrame
```

**Effort:** Low — pure CSS/SVG animation on the existing `ScoreRing` component.

---

### Proposal D — Typing Indicator with Waveform During Streaming

**Problem:** While the Forge LLM is streaming, there's no visual indicator of "it's still thinking" between chunks.

**Design:** During any streaming gap > 300ms (no new token), the existing `WaveformIcon` component (`AgentActivityIcon.tsx`) appears inline at the end of the message being composed, then disappears as new tokens arrive. This uses the existing `af-wave` animation — no new CSS needed.

```tsx
// In ChatUI: if (isStreaming && timeSinceLastToken > 300) show <WaveformIcon />
```

**Effort:** Very low — waveform component already exists. Just wire the timing logic.

---

### Proposal E — Card Hover State with Depth Shadow + Glow

**Problem:** Agent cards on `/agents` have a flat hover state (just a border color change). Cards feel like a table, not an interactive surface.

**Design:** On hover, cards lift 3px (`translateY(-3px)`) and emit a soft violet glow shadow. The card's gradient border brightens. This builds on the existing `.af-hover-lift` utility but adds the color-aware glow.

```css
/* Extend af-hover-lift with glow */
.af-card-interactive:hover {
  transform: translateY(-3px);
  box-shadow:
    0 16px 48px -12px rgba(124, 58, 237, 0.2),
    0 0 0 1px rgba(195, 192, 255, 0.12);
}
```

**Effort:** Very low — CSS only, apply to agent/campaign/knowledge cards.

---

### Proposal F — Execution Timeline Visualization `[SHIPPED]`

**Problem:** The execution detail page shows a flat log. Understanding the time breakdown between nodes requires mental arithmetic.

**Design:** Add a horizontal timeline strip at the top of the execution detail. Each node is a colored bar segment proportional to its duration. Click a segment → scroll to that node's log section. Tooltip shows: node name, duration, token count.

```
[START] ██▓ LLM (1.2s) ██ Tool (0.4s) ██▓ LLM (0.8s) [END]
         ─────────────────────────────────────────────────
         Total: 2.4s  ·  4 nodes  ·  1,240 tokens
```

**Effort:** Medium — needs execution node timing data from the API (may need enriching the execution response schema).

---

### Proposal G — Ambient Sound Mode (opt-in) `[SHIPPED]`

**Problem:** Long fine-tune jobs or campaign runs have no feedback — users forget they're running.

**Design:** Optional ambient sound that plays a subtle chime when an execution completes or a campaign finishes. Off by default, toggled in `/settings/preferences`. Uses the Web Audio API with a generated tone (no asset files needed).

```ts
// Two-note ascending chime: C5 (523Hz, 60ms) → E5 (659Hz, 80ms) with quick envelope
const audioCtx = new AudioContext();
// ... oscillator + gain envelope
```

**Effort:** Low — pure Web Audio API, ~20 lines. Toggle in localStorage.

---

## File Map (state: 2026-04-07)

```
backend/
  app/
    domain/entities/            agent, execution, skill, campaign, finetune_job,
                                schedule, speech_example, voice_sample, user
                                [PLANNED] memory
    domain/ports/               orchestrator, agent_repo, campaign_repo, knowledge_repo,
                                skill_repo, finetune_repo, execution_events, sandbox, redteam
                                [PLANNED] memory_store
    application/services/       agent_service, campaign_service, finetune_service,
                                forge_service, knowledge_service, skill_service,
                                generation_service, auth_service, secrets_service
    infrastructure/
      orchestration/            langgraph_orchestrator (7 node types), llm_invoke,
                                context_manager, cost_meter, checkpoint_registry
      persistence/postgres/     models (20 ORM), all repos
      integrations/             tavily, python_repl, huggingface, file_tools, google_api
      speech/                   openai_whisper, openai_tts, elevenlabs_tts, http_finetuned_*
      redteam/                  promptfoo_engine, mock_engine, config_generator
      scheduling/               tick.py (cron worker)
      webhooks/                 delivery.py (outbound only — inbound [PLANNED])
      observability/            langfuse_span_emitter, langsmith_span_emitter
      events/                   redis_execution_stream
      sandbox/                  subprocess + docker
      memory/                   [PLANNED] — entirely missing
    api/v1/                     agents, auth, campaigns, finetune, forge, knowledge,
                                skills, speech, sandbox, settings, templates, webhooks,
                                generation, dashboard
  modal_functions/
    train.py                    [PARTIAL] stub — real training not implemented
    train_speech.py             [PARTIAL] stub

frontend/
  src/
    app/                        dashboard, agents (list/new/[id]/builder), skills, knowledge,
                                finetune, campaigns, forge, sandbox, executions, chat,
                                settings, profile, login, register, auth/callback
    components/
      agent/                    AgentActivityIcon, AgentStepChips, AgentToastStack
      campaign/                 ScoreRing
      chat/                     ChatSlideOver, ChatUI, FloatingChatButton, MarkdownMessage
      dashboard/                OnboardingChecklist [SHIPPED], ActivityFeed, StatCard, QuickActions
      execution/                ExecutionLog, InterruptModal, InterruptPopup, VoiceTestButton
      layout/                   AppHeader, AsciiField, AuroraBackground, ToolShell, ThemeToggle
      builder/                  [PLANNED] InspectorPanel, node forms (color-coded by type)
      ui/                       EmptyState [SHIPPED], OnboardingChecklist [SHIPPED]
    hooks/                      useAgentActivity
                                [PLANNED] useAutoResize (textarea)
    lib/                        api.ts, sse.ts, onboarding.ts [SHIPPED]

sdk/                            LocalAgent, AgentBuilder, CLI, speech providers [SHIPPED]
sdk-js/                         AgentClient, AgentBuilder, CLI, types [SHIPPED]
sdk-client/                     Full HTTP client — all API modules [SHIPPED]
mcp-server/                     18 tools covering full API surface [SHIPPED]

docs/superpowers/
  plans/                        2026-04-01-agentforge-roadmap.md
                                2026-04-04-long-term-memory.md (not started)
  specs/                        design specs
  AGENTFORGE_ROADMAP.md         this file
```

---

*Updated: 2026-04-07 — Nicolas Edmond — Formalis.IA*
*Based on full codebase analysis: backend services, ORM models, migrations, API routes, frontend pages, SDK packages.*
