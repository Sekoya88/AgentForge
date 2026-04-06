# AgentForge — Roadmap (Mise à jour 2026-04-06)

> **Analyse de base :** Ce document reflète l'état réel du codebase au 2026-04-06. Chaque axe liste ce qui est implémenté et ce qui reste à construire. Les tâches sont ordonnées par valeur / dépendances.

---

## ÉTAT ACTUEL — Ce qui est déjà livré

### Backend complet

- **Orchestrateur LangGraph** — 7 types de nœuds : `llm`, `tool`, `conditional`, `interrupt`, `subagent`, `asr`, `tts`
- **Forge** — assistant direct multi-provider (Anthropic, OpenAI, Gemini) avec 8 outils (web_search, python_repl, list_agents, HuggingFace search, read/write_file)
- **RAG hybride** — BM25 + sémantique pgvector avec RRF fusion, chunking structurel avec heading_context
- **Campagnes red-team** — Promptfoo réel + Mock engine, score de sécurité écrit sur l'agent
- **Fine-tuning** — Intégration Modal (text_sft, whisper, tts_voice), auto-deploy shadow alias, dataset management
- **Schedules** — Cron worker, CRUD complet, tick toutes les 60s
- **Speech** — ASR (Whisper + finetuned HTTP), TTS (OpenAI + ElevenLabs + finetuned HTTP), audio execution endpoint
- **Observabilité** — Langfuse `@observe` sur orchestrateur, llm_invoke, forge ; `langfuse_span_emitter` pour tous les SSE events ; enrichissement user/session/execution
- **Webhooks** — Delivery HTTP pour `execution_completed` et `campaign_completed`
- **Versioning** — snapshots d'agents, aliases (production/staging), rollback, diff
- **Context management** — sliding window + compression LLM automatique
- **Exécution policy** — allowlist/denylist d'outils, pattern blocking, human approval, max_cost, max_steps

### Frontend complet

- **Builder visuel** — React Flow, tous les types de nœuds (llm, tool, conditional, interrupt, subagent, asr, tts)
- **Forge UI** — multi-onglets, slash commands, streaming tokens, activity toasts
- **Chat** — multi-agents, multi-conversations, slide-over + plein écran, SSE activity animations
- **Animations SSE** — `AgentStepChips`, `AgentToastStack`, `AgentActivityIcon` stylisés avec le thème de l'app
- **Pages** — dashboard, agents, builder, skills, knowledge, finetune, campaigns, executions, sandbox, settings, profile

### SDKs

- **SDK Python** (`sdk/`) — `LocalAgent`, `AgentBuilder` fluent API, CLI (`validate`, `compile`, `run`, `pull`, `push`, `batch-score`), node types complets, speech providers
- **SDK TypeScript** (`sdk-js/`) — `AgentClient`, `AgentBuilder`, CLI, types générés OpenAPI
- **SDK Client Python** (`sdk-client/`) — HTTP client async (httpx), agents + schedules CRUD

---

## AXE 1 — COMPLÉTER L'EXISTANT (P0 — Quick wins)

### TASK 1.1 — MCP Server — Exposer toute l'API (était : 2 tools sur ~40)

**Situation actuelle :** `mcp-server/src/agentforge_mcp/server.py` n'expose que `list_agents` et `execute_agent`.

**À ajouter dans `mcp-server/src/agentforge_mcp/server.py` :**

```python
# Tools manquants à implémenter avec FastMCP

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

**Tâches :**

1. Implémenter les 11 tools manquants
2. Ajouter auth token dans le header des calls HTTP (`Authorization: Bearer {token}`)
3. Publier sur npm : `@agentforge/mcp`
4. Documenter dans `mcp-server/README.md` avec config Cursor/Claude

---

### TASK 1.2 — Fine-tuning Modal — Écrire le vrai code d'entraînement

**Situation actuelle :** `modal_functions/train.py` est un **stub entièrement commenté**. `FinetuneService` appelle `modal.Function.from_name("agentforge-finetune", "train_model")` mais cette fonction n'existe pas en prod.

**Fichiers :**

- `backend/modal_functions/train.py` — à implémenter avec Unsloth/TRL
- `backend/modal_functions/train_speech.py` — ASR/TTS fine-tuning (état : commenté)

**Tâches :**

1. Implémenter `train_model()` Modal avec Unsloth QLoRA (text_sft) sur GPU A100
2. Implémenter `train_speech_model()` (whisper + xtts/bark pour tts_voice)
3. Écrire les logs de loss vers la DB via callback Modal → FastAPI webhook
4. Tester le flow complet : upload dataset JSONL → trigger → deploy → inference-stream

---

### TASK 1.3 — SDK Client Python — Couvrir tout l'API

**Situation actuelle :** `sdk-client/` couvre seulement agents, schedules, et quelques routes speech.

**À compléter dans `sdk-client/src/agentforge_client/` :**

```python
# Modules manquants
skills.py      # CRUD skills
knowledge.py   # ingest, search, list_sources, delete
campaigns.py   # launch, get, report, delete
finetune.py    # create, get, list, deploy, trigger
forge.py       # conversations + execute + stream
executions.py  # list, get, feedback, interrupt
webhooks.py    # CRUD webhooks
generation.py  # generate_agent, generate_skill
```

**Tâches :**

1. Créer un module par domaine
2. Couvrir tous les endpoints de `backend/app/api/v1/`
3. Générer les types depuis `openapi/openapi.json`
4. Publier sur PyPI : `pip install agentforge-client`

---

### TASK 1.4 — Knowledge — Ingestion PDF et URLs

**Situation actuelle :** Seuls `POST /knowledge/ingest` (texte brut) et `POST /knowledge/upload` (fichier) sont implémentés. Pas de PDF parsing ni de web crawling.

**Fichiers :**

- `backend/app/application/services/knowledge_service.py`
- `backend/app/api/v1/knowledge.py`

**Tâches :**

1. Ajouter parsing PDF avec `pypdf` ou `pdfplumber` : `ingest_pdf(file_bytes, source_title)`
2. Ajouter crawling URL avec `httpx` + `BeautifulSoup` : `ingest_url(url)` (fetch → strip HTML → chunk)
3. Supporter GitHub README + docs via URL GitHub raw
4. Ajouter endpoint `POST /knowledge/ingest-url` avec `{"url": "..."}`
5. Exposer le type de source dans `KnowledgeSourceSummary` (text / pdf / url)

---

### TASK 1.5 — Webhooks — Couvrir plus d'événements

**Situation actuelle :** Seuls `execution_completed` et `campaign_completed` sont livrés.

**Événements manquants dans `infrastructure/webhooks/delivery.py` :**

```python
WEBHOOK_EVENTS = {
    "execution_completed",   # ✅ implémenté
    "campaign_completed",    # ✅ implémenté
    "execution_started",     # ❌ manquant
    "execution_failed",      # ❌ manquant
    "schedule_fired",        # ❌ manquant
    "finetune_completed",    # ❌ manquant
    "agent_updated",         # ❌ manquant
}
```

**Tâches :**

1. Émettre `execution_started` depuis `AgentService.execute()` juste après création en DB
2. Émettre `execution_failed` depuis `_run_background()` sur exception
3. Émettre `schedule_fired` depuis `schedule_worker_loop()`
4. Émettre `finetune_completed` depuis le poll loop dans `FinetuneService`
5. Émettre `agent_updated` depuis `AgentService.update()`
6. Ajouter filtrage par événement dans la config webhook (`{"events": ["execution_completed"]}`)

---

## AXE 2 — MÉMOIRE AGENT (P0 — Entièrement manquant)

### TASK 2.1 — Mémoire persistante (Long-Term Memory)

**Situation actuelle :** Aucune implémentation de mémoire. Le plan `2026-04-04-long-term-memory.md` existe mais n'a pas démarré.

**Architecture cible :**

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
    importance: float  # 0.0-1.0
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

**Tâches :**

1. Créer `backend/app/domain/entities/memory.py` et `backend/app/domain/ports/memory_store.py`
2. Créer ORM `AgentMemoryModel` dans `models.py` (pgvector pour embedding)
3. Alembic migration : table `agent_memories` avec index HNSW
4. Implémenter `PgvectorMemoryStore` dans `infrastructure/memory/`
5. Ajouter nœuds `memory_save` et `memory_recall` dans l'orchestrateur LangGraph
6. Ajouter types `"memory_save"` et `"memory_recall"` dans le builder UI
7. API : `GET/DELETE /api/v1/agents/{id}/memories`

---

## AXE 3 — BUILDER VISUEL — AMÉLIORATIONS (P1)

### TASK 3.1 — Node Inspector Panel (édition inline)

**Situation actuelle :** La config des nœuds est inline dans le canevas. Chaque type de nœud a un petit panneau embedded dans le node lui-même.

**Cible :** Un panneau latéral dédié qui s'ouvre au clic sur un nœud, avec formulaire typé par nœud, validation Zod live, et auto-save.

**Fichiers :**

- `frontend/src/app/agents/[id]/builder/page.tsx` (modifier)
- `frontend/src/components/builder/InspectorPanel.tsx` (créer)
- `frontend/src/components/builder/forms/` (créer : LLMNodeForm, ToolNodeForm, etc.)

**Tâches :**

1. Extraire `useSelectedNode` hook (wraps React Flow `getNode`)
2. Créer `InspectorPanel` composant avec dispatch sur le type de nœud
3. Créer un FormComponent par type : LLM, Tool, Conditional, Interrupt, Subagent, ASR, TTS
4. Validation Zod inline avec messages d'erreur temps réel
5. Auto-save debounce 500ms → `PUT /api/v1/agents/{id}`
6. Indicateur "unsaved changes" dans la topbar

---

### TASK 3.2 — Nœuds manquants dans le builder UI

**Situation actuelle :** Le backend supporte le type `"tool"` avec `tool_name: "retrieve"` (RAG) mais le builder n'a pas de panneau dédié pour la configuration RAG. De même, pas de nœud "code" (python_repl) malgré le support backend.

**Tâches :**

1. Ajouter nœud **Retrieval** dans le builder (type `tool` avec `tool_name: retrieve`, config `top_k`)
2. Ajouter nœud **Code** (type `tool` avec `tool_name: python_repl`)
3. Ajouter nœud **Memory Save** / **Memory Recall** (dépend de Task 2.1)
4. Ajouter panneau de config pour les nœuds Google Workspace (read_gmail, create_calendar_event)

---

### TASK 3.3 — Undo/Redo + Keyboard Shortcuts + Auto-layout

**Tâches :**

1. Undo/redo avec Zustand + snapshots du graph state (`Ctrl+Z` / `Ctrl+Y`)
2. Auto-layout avec `@dagrejs/dagre` (bouton "Arrange" ou `Ctrl+Shift+L`)
3. Keyboard shortcuts : `Ctrl+S` save, `Ctrl+D` duplicate nœud sélectionné, `Delete` supprimer nœud
4. Activer `<MiniMap>` React Flow (déjà disponible dans la lib)

---

## AXE 4 — OBSERVABILITÉ ET ANALYTICS (P1)

### TASK 4.1 — Dashboard métriques temps réel

**Situation actuelle :** `GET /api/v1/dashboard` retourne uniquement des stats agrégées basiques (counts). Pas de time-series, pas de latence P95, pas de coût estimé.

**Endpoints à créer dans `backend/app/api/v1/dashboard.py` :**

```python
GET /api/v1/dashboard/metrics?agent_id=&from=&to=&granularity=hour
# → { executions_by_hour, avg_latency_ms, p95_latency_ms, token_usage, estimated_cost_usd, error_rate }

GET /api/v1/dashboard/agents/{id}/timeline
# → time-series d'exécutions + scores

GET /api/v1/dashboard/agents/{id}/node-perf
# → latence par nœud sur les N dernières exécutions
```

**Tâches :**

1. Ajouter table `execution_node_metrics` (ou enrichir les spans Langfuse existants)
2. Implémenter les 3 endpoints d'agrégation
3. Page frontend `/analytics` avec Recharts : line charts latence, bar charts tokens, heatmap erreurs
4. Export CSV des métriques

---

### TASK 4.2 — LangSmith — Compléter l'intégration

**Situation actuelle :** `langsmith_span_emitter.py` existe mais LangSmith n'a pas les `@observe` decorators de Langfuse. L'intégration est event-based seulement.

**Tâches :**

1. Vérifier que `langsmith_span_emitter` est bien branché dans `agent_service.py` (vérifier si `LANGSMITH_API_KEY` active le bon emitter)
2. Ajouter un `@trace` LangSmith sur `agent_run` et `forge_run` (équivalent des `@observe` Langfuse)
3. Documenter le switch Langfuse vs LangSmith dans `docs/`

---

## AXE 5 — EDGE CONDITIONS ET ROUTING AVANCÉ (P1)

### TASK 5.1 — Opérateurs de condition étendus

**Situation actuelle :** Le nœud `conditional` supporte seulement : `always`, `contains`, `regex`, `json_path`. Pas de scoring, pas de comparaison numérique, pas de AND/OR composé.

**Fichiers :**

- `backend/app/infrastructure/orchestration/langgraph_orchestrator.py` (routing logic)
- `backend/app/domain/graph_definition.py` (EdgeCondition schema)

**Opérateurs à ajouter :**

```python
OPERATORS = {
    "contains": ...,     # ✅ existe
    "regex": ...,        # ✅ existe
    "json_path": ...,    # ✅ existe
    "always": ...,       # ✅ existe
    "equals": ...,       # ❌ manquant
    "gt": ...,           # ❌ manquant (score > seuil)
    "lt": ...,           # ❌ manquant
    "not_contains": ..., # ❌ manquant
    "and": ...,          # ❌ manquant (conditions composées)
    "or": ...,           # ❌ manquant
}
```

**Tâches :**

1. Étendre `EdgeCondition` dans `graph_definition.py`
2. Implémenter les nouveaux opérateurs dans l'orchestrateur
3. Ajouter `EdgeRuleBuilder` composant dans le builder UI (visual rule builder)
4. Ajouter mode "test condition" : input exemple → quelle branche serait prise

---

## AXE 6 — EXPORT ET PORTABILITÉ (P1)

### TASK 6.1 — Format AFG v2 et export multi-format

**Situation actuelle :** Export/import est implémenté en JSON interne (via `POST /agents/import-bundle`). Pas d'export vers Python standalone, Docker, ou LangSmith.

**Cible :**

```bash
# CLI SDK
agentforge export agent-id --format python    # → agent_standalone.py
agentforge export agent-id --format docker    # → Dockerfile + agent.py
agentforge export agent-id --format langgraph # → langgraph_config.json

# API
POST /api/v1/agents/{id}/export?format=python
POST /api/v1/agents/{id}/export?format=docker
POST /api/v1/agents/{id}/export?format=langgraph
```

**Tâches :**

1. Créer `backend/app/application/export_service.py` avec les 3 formats
2. Créer `sdk/agentforge/exporters/python_exporter.py` → script standalone autonome
3. Créer `sdk/agentforge/exporters/docker_exporter.py` → Dockerfile minimal
4. Ajouter les endpoints API correspondants
5. Ajouter boutons "Export as Python / Docker" dans l'agent detail page

---

### TASK 6.2 — Runtime Standalone (sans FastAPI)

**Situation actuelle :** Le `sdk/agentforge/cli.py` existe avec `run` et `push`, mais pas de serveur HTTP minimal pour exposer un agent exporté.

**Cible :**

```bash
agentforge serve agent.afg.yaml --port 8080
# → expose POST /execute et GET /stream/:id
```

**Tâches :**

1. Créer `sdk/agentforge/runtime/server.py` (FastAPI ultra-minimal : 3 routes)
2. Créer `sdk/agentforge/runtime/loader.py` (charge `.afg.yaml` → `LocalAgent`)
3. Brancher dans le CLI existant : `agentforge serve <file>`
4. Tester : export d'un agent → `agentforge serve` → curl execute

---

## AXE 7 — QUALITÉ ET ROBUSTESSE (P1)

### TASK 7.1 — Coverage tests à 80%

**Situation actuelle :** `backend/coverage.xml` présent. Tests dans `backend/tests/unit/` (récemment créé).

**Tâches :**

1. `cd backend && pytest --cov=app --cov-report=html` → analyser les gaps réels
2. Tests unitaires pour tous les services application (`tests/application/`)
3. Tests d'intégration pour les routes API critiques (agents, execute, campaigns)
4. Tests pour l'orchestrateur LangGraph (mock LLM provider via `FakeListChatModel`)
5. CI : ajouter seuil `--cov-fail-under=80` dans `.github/workflows/backend.yml`

---

### TASK 7.2 — Error Handling structuré

**Situation actuelle :** Erreurs propagées comme exceptions Python brutes ou `HTTPException` generiques. Pas de hiérarchie domain.

**Tâches :**

1. Créer `backend/app/domain/exceptions.py` : `DomainException`, `AgentNotFoundError`, `ExecutionFailedError`, `SkillValidationError`, etc.
2. Exception handler FastAPI global : `{"error": {"code": "AGENT_NOT_FOUND", "message": "...", "request_id": "..."}}`
3. Frontend : parser les codes d'erreur structurés → toasts contextuels avec action suggérée

---

### TASK 7.3 — Voice Sample Storage — Passer à S3

**Situation actuelle :** `voice_sample_repo.py` stocke l'audio en base64 dans PostgreSQL. Le code comporte un commentaire explicite indiquant "use object storage at scale".

**Tâches :**

1. Ajouter `S3_BUCKET` et `S3_ENDPOINT_URL` dans `.env` / `config.py`
2. Créer `infrastructure/storage/s3_store.py` avec `upload_audio(bytes) → url`
3. Modifier `voice_sample_repo.py` pour stocker l'URL S3 plutôt que le base64
4. Migration Alembic : `audio_data TEXT → audio_url TEXT`

---

## AXE 8 — ÉCOSYSTÈME (P2)

### TASK 8.1 — AgentForge Hub (marketplace interne)

**Situation actuelle :** Pas de page Hub. Les agents ont `is_public: bool` dans l'entité mais pas d'endpoint public listing.

**Tâches :**

1. Ajouter `stars: int` sur la table `agents`
2. Créer `GET /api/v1/hub/agents` (agents publics, paginés, filtrés par catégorie)
3. Créer `POST /api/v1/hub/agents/{id}/clone`
4. Créer page frontend `/hub` avec grid + filtres par catégorie
5. Ajouter bouton "Publish to Hub" dans l'agent detail page

---

### TASK 8.2 — Webhooks Triggers (Inbound)

**Situation actuelle :** `WebhookSubscription` ORM model et table existent. L'endpoint `POST /api/v1/webhooks` est implémenté pour les webhooks **sortants** (outbound delivery). Il manque les webhooks **entrants** (triggers).

**Tâches :**

1. Créer `POST /api/v1/agents/{id}/webhook/:secret` — reçoit un payload externe → déclenche l'agent
2. Générer un secret par agent à la création (`secrets.token_urlsafe(32)`)
3. Documenter dans le builder UI : "Copy webhook URL" avec secret

---

### TASK 8.3 — SDK Python — Publication PyPI

**Situation actuelle :** `sdk/pyproject.toml` est configuré mais le package n'est pas publié.

**Tâches :**

1. `cd sdk && python -m build`
2. `twine upload --repository testpypi dist/*` (TestPyPI d'abord)
3. Vérifier `pip install agentforge-sdk --index-url testpypi`
4. Publication finale sur PyPI : `twine upload dist/*`
5. Ajouter badge PyPI dans le README

---

## ORDRE D'EXÉCUTION RECOMMANDÉ

```
SPRINT 1 — Finir l'existant (2 semaines)
  → TASK 1.2  Fine-tuning Modal (vrai code training)
  → TASK 1.4  Knowledge : ingestion PDF + URLs
  → TASK 1.5  Webhooks : 5 événements manquants
  → TASK 1.1  MCP Server : 11 tools manquants

SPRINT 2 — Mémoire et Builder (2 semaines)
  → TASK 2.1  Long-Term Memory (entité + infrastructure + UI)
  → TASK 3.1  Node Inspector Panel
  → TASK 3.2  Nœuds manquants (Retrieval, Code, Memory)

SPRINT 3 — Analytics et Qualité (1 semaine)
  → TASK 4.1  Dashboard métriques
  → TASK 7.1  Coverage tests 80%
  → TASK 7.2  Error handling structuré
  → TASK 3.3  Undo/redo + keyboard shortcuts

SPRINT 4 — Portabilité et Écosystème (2 semaines)
  → TASK 6.1  Export AFG v2 multi-format
  → TASK 6.2  Runtime standalone
  → TASK 1.3  SDK Client Python complet → PyPI
  → TASK 8.3  SDK Python → PyPI

SPRINT 5 — Hub et Triggers (1 semaine)
  → TASK 8.1  AgentForge Hub
  → TASK 8.2  Webhooks inbound triggers
  → TASK 5.1  Edge conditions étendues
```

---

## FICHIERS CLÉS DU PROJET (état 2026-04-06)

```
backend/
  app/
    domain/entities/            agent, execution, skill, campaign, finetune_job,
                                schedule, speech_example, voice_sample, user
                                ❌ memory (manquant)
    domain/ports/               orchestrator, agent_repo, campaign_repo, knowledge_repo,
                                skill_repo, finetune_repo, execution_events, sandbox, redteam
                                ❌ memory_store (manquant)
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
      webhooks/                 delivery.py (outbound)
      observability/            langfuse_span_emitter, langsmith_span_emitter
      events/                   redis_execution_stream
      sandbox/                  subprocess + docker
      memory/                   ❌ entièrement manquant
    api/v1/                     agents, auth, campaigns, finetune, forge, knowledge,
                                skills, speech, sandbox, settings, templates, webhooks,
                                generation, dashboard
  modal_functions/
    train.py                    ❌ stub commenté — training réel non implémenté
    train_speech.py             ❌ stub commenté

frontend/
  src/
    app/                        dashboard, agents (list/new/[id]/builder), skills, knowledge,
                                finetune, campaigns, forge, sandbox, executions, chat,
                                settings, profile, login, register, auth/callback
    components/
      agent/                    AgentActivityIcon, AgentStepChips, AgentToastStack
      campaign/                 ScoreRing
      chat/                     ChatSlideOver, ChatUI, FloatingChatButton, MarkdownMessage
      execution/                ExecutionLog, InterruptModal, InterruptPopup, VoiceTestButton
      layout/                   AppHeader, AsciiField, AuroraBackground, ToolShell, ThemeToggle
    hooks/                      useAgentActivity
    lib/                        api.ts, sse.ts

sdk/                            LocalAgent, AgentBuilder, CLI, speech providers ✅
sdk-js/                         AgentClient, AgentBuilder, CLI, types ✅
sdk-client/                     HTTP client Python (partiel — agents + schedules seulement)
mcp-server/                     2 tools seulement (list_agents, execute_agent) ❌

docs/superpowers/
  plans/                        2026-04-01-agentforge-roadmap.md (en cours)
                                2026-04-04-long-term-memory.md (pas démarré)
  specs/                        specs de design
  AGENTFORGE_ROADMAP.md         ce fichier
```

---

*Mise à jour : 2026-04-06 — Nicolas Edmond — Formalis.IA*
*Basé sur analyse complète du codebase réel, git log, et état des plans existants.*
