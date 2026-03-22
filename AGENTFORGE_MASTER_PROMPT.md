# AgentForge — Master Build Prompt

> **Objectif** : Ce fichier est un **mega-prompt** destiné à être injecté dans un agent de développement (Claude Code + GSD, Cursor, Windsurf, ou tout agent de coding) pour construire AgentForge de bout en bout. Il contient la spec complète, l'architecture, les contraintes techniques, les user stories, le schéma de données, les API contracts, et les instructions de déploiement.

---

## 0. Identité du Projet

```yaml
project_name: AgentForge
tagline: "Build, Red-Team & Ship LLM Agents — From Prototype to Production"
type: Full-stack platform (Backend API + Frontend SPA)
author: Nicolas Edmond
license: MIT
repo_structure: monorepo
```

---

## 1. Vision & Problème Résolu

### Problème

Aujourd'hui, déployer un agent LLM en production implique :

1. **Pas de pipeline de sécurité standard** — Les équipes testent manuellement leurs prompts, sans couverture systématique des vulnérabilités (prompt injection, jailbreak, data exfiltration, tool misuse).
2. **Fragmentation des outils** — L'orchestration (LangGraph), l'évaluation (promptfoo), le fine-tuning (Unsloth) et l'infrastructure (Modal) sont des outils séparés sans intégration.
3. **Pas de human-in-the-loop industrialisé** — Les interrupts et validations humaines sont implémentés ad hoc, sans interface unifiée.
4. **Pas de sandbox** — Les développeurs testent directement en staging/prod sans environnement isolé pour expérimenter.

### Solution

AgentForge est une plateforme unifiée qui permet de :

- **Concevoir** des pipelines agentic multi-étapes via un builder visuel (LangGraph + Deep Agents pattern)
- **Sécuriser** automatiquement chaque agent via des campagnes de red-teaming (promptfoo, OWASP LLM Top 10, NIST AI RMF)
- **Spécialiser** des modèles via fine-tuning serverless (Unsloth QLoRA sur Modal GPU)
- **Contrôler** l'exécution avec human-in-the-loop configurable par outil
- **Expérimenter** dans une sandbox isolée avec système de skills extensible

---

## 2. Stack Technique

### Backend

| Composant | Technologie | Justification |
|---|---|---|
| Runtime Python | **Python 3.12+** | Compatibilité LangGraph, Unsloth, FastAPI |
| Framework API | **FastAPI** | Async natif, SSE streaming, Pydantic validation, OpenAPI auto-docs |
| Orchestration Agents | **LangGraph** + **deepagents** SDK | Graphe d'agents avec checkpointing, interrupts, sub-agents, planning tool |
| Red-Teaming | **promptfoo** (CLI + programmatic) | 50+ plugins de vulnérabilités, génération automatique, scoring |
| Fine-Tuning | **Unsloth** (QLoRA/LoRA) | 2x speedup, 70% memory reduction, compatible HF Transformers |
| Infrastructure GPU | **Modal** | Serverless GPU (A10G/A100), scale-to-zero, $30/mois free tier |
| Base de données | **PostgreSQL 16** + **pgvector** | Stockage relationnel + vector search pour RAG |
| Cache & State | **Redis** | Checkpointing LangGraph, cache de sessions, pub/sub pour SSE |
| ORM | **SQLAlchemy 2.0** + **Alembic** | Async support, migrations |
| Validation | **Pydantic v2** | Schemas stricts, serialization JSON |
| Auth | **JWT** (via python-jose) + **OAuth2** | Sécurisation API, gestion utilisateurs |
| Task Queue | **Celery** ou **Modal** functions | Jobs longs (fine-tuning, red-team campaigns) |
| Containerisation | **Docker** + **Docker Compose** | Dev local, déploiement |

### Frontend

| Composant | Technologie | Justification |
|---|---|---|
| Framework | **Next.js 15** (App Router) | SSR, RSC, API routes, excellent DX |
| UI Library | **React 19** | Composants, hooks, suspense |
| Styling | **Tailwind CSS v4** + **shadcn/ui** | Rapid prototyping, composants accessibles |
| State Management | **Zustand** ou **TanStack Query** | Lightweight, cache serveur |
| Graphe Visualisation | **React Flow** | Builder visuel de graphes d'agents (drag-and-drop nodes/edges) |
| Charts | **Recharts** ou **Tremor** | Dashboard red-team, métriques fine-tuning |
| Real-time | **EventSource** (SSE) | Streaming logs d'exécution agent |
| Forms | **React Hook Form** + **Zod** | Validation côté client |

### DevOps & Tooling

| Composant | Technologie |
|---|---|
| CI/CD | **GitHub Actions** |
| Linting | **Ruff** (Python), **ESLint** + **Prettier** (TS) |
| Testing Backend | **pytest** + **pytest-asyncio** |
| Testing Frontend | **Vitest** + **Playwright** |
| Dev Workflow | **GSD** (Get Shit Done) — spec-driven, atomic commits |
| Containerisation | **Docker Compose** (dev), **Kubernetes** (prod) |
| Monitoring | **Langfuse** (observabilité LLM) + **Sentry** (errors) |

---

## 3. Architecture Détaillée

### 3.1 Clean Architecture — Structure du Monorepo

```
agentforge/
├── .gsd/                          # GSD planning files (auto-generated)
├── .planning/                     # GSD roadmap, phases, milestones
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── config.py              # Settings (Pydantic BaseSettings)
│   │   ├── dependencies.py        # Dependency injection
│   │   │
│   │   ├── domain/                # === DOMAIN LAYER (pure business logic) ===
│   │   │   ├── entities/
│   │   │   │   ├── agent.py       # Agent, AgentNode, AgentEdge entities
│   │   │   │   ├── campaign.py    # RedTeamCampaign, Vulnerability entities
│   │   │   │   ├── skill.py       # Skill, SkillRegistry entities
│   │   │   │   ├── fine_tune.py   # FineTuneJob, Dataset entities
│   │   │   │   └── user.py        # User, Team entities
│   │   │   ├── value_objects/
│   │   │   │   ├── agent_config.py
│   │   │   │   ├── security_score.py
│   │   │   │   └── model_config.py
│   │   │   ├── events/
│   │   │   │   ├── agent_events.py      # AgentCreated, AgentExecutionStarted, InterruptTriggered
│   │   │   │   ├── campaign_events.py   # CampaignStarted, VulnerabilityDetected
│   │   │   │   └── finetune_events.py   # TrainingStarted, TrainingCompleted
│   │   │   └── ports/                   # === PORTS (interfaces) ===
│   │   │       ├── agent_repository.py        # ABC for agent persistence
│   │   │       ├── campaign_repository.py     # ABC for campaign persistence
│   │   │       ├── agent_orchestrator.py      # ABC for LangGraph execution
│   │   │       ├── redteam_engine.py          # ABC for promptfoo integration
│   │   │       ├── finetune_service.py        # ABC for Unsloth/Modal
│   │   │       ├── sandbox_runtime.py         # ABC for sandbox execution
│   │   │       └── event_bus.py               # ABC for event publishing
│   │   │
│   │   ├── application/           # === APPLICATION LAYER (use cases) ===
│   │   │   ├── commands/
│   │   │   │   ├── create_agent.py
│   │   │   │   ├── execute_agent.py
│   │   │   │   ├── approve_interrupt.py
│   │   │   │   ├── launch_campaign.py
│   │   │   │   ├── start_finetune.py
│   │   │   │   ├── create_skill.py
│   │   │   │   └── deploy_model.py
│   │   │   ├── queries/
│   │   │   │   ├── get_agent.py
│   │   │   │   ├── get_campaign_report.py
│   │   │   │   ├── get_finetune_status.py
│   │   │   │   └── list_skills.py
│   │   │   └── services/
│   │   │       ├── agent_service.py
│   │   │       ├── redteam_service.py
│   │   │       ├── finetune_service.py
│   │   │       └── sandbox_service.py
│   │   │
│   │   ├── infrastructure/        # === INFRASTRUCTURE LAYER (adapters) ===
│   │   │   ├── persistence/
│   │   │   │   ├── postgres/
│   │   │   │   │   ├── models.py          # SQLAlchemy ORM models
│   │   │   │   │   ├── agent_repo.py      # Implements AgentRepository
│   │   │   │   │   ├── campaign_repo.py   # Implements CampaignRepository
│   │   │   │   │   └── session.py         # Async session factory
│   │   │   │   └── redis/
│   │   │   │       ├── cache.py
│   │   │   │       └── checkpointer.py    # LangGraph Redis checkpointer
│   │   │   ├── orchestration/
│   │   │   │   ├── langgraph_orchestrator.py   # LangGraph graph builder
│   │   │   │   ├── deep_agent_factory.py       # Deep Agents SDK wrapper
│   │   │   │   ├── tools/                      # Custom LangGraph tools
│   │   │   │   │   ├── rag_tool.py
│   │   │   │   │   ├── web_search_tool.py
│   │   │   │   │   └── code_execution_tool.py
│   │   │   │   └── middleware/
│   │   │   │       ├── interrupt_handler.py     # Human-in-the-loop middleware
│   │   │   │       ├── context_compressor.py    # Deep Agents context management
│   │   │   │       └── logging_middleware.py     # Execution logging
│   │   │   ├── redteam/
│   │   │   │   ├── promptfoo_adapter.py    # Implements RedTeamEngine port
│   │   │   │   ├── config_generator.py     # Generates promptfoo YAML from agent config
│   │   │   │   ├── report_parser.py        # Parses promptfoo JSON output
│   │   │   │   └── plugins/                # Custom promptfoo plugins
│   │   │   │       └── custom_policy.py
│   │   │   ├── finetune/
│   │   │   │   ├── modal_runtime.py        # Modal GPU provisioning
│   │   │   │   ├── unsloth_trainer.py      # Unsloth QLoRA training loop
│   │   │   │   ├── dataset_processor.py    # Dataset validation & formatting
│   │   │   │   └── model_deployer.py       # Deploy fine-tuned model as endpoint
│   │   │   ├── sandbox/
│   │   │   │   ├── modal_sandbox.py        # Modal Sandbox runtime
│   │   │   │   ├── docker_sandbox.py       # Local Docker sandbox (fallback)
│   │   │   │   └── skill_loader.py         # Load & validate skills
│   │   │   ├── auth/
│   │   │   │   ├── jwt_handler.py
│   │   │   │   └── oauth2.py
│   │   │   └── events/
│   │   │       ├── redis_event_bus.py      # Redis pub/sub event bus
│   │   │       └── sse_broadcaster.py      # SSE streaming to frontend
│   │   │
│   │   └── api/                   # === API LAYER (controllers) ===
│   │       ├── v1/
│   │       │   ├── agents.py          # CRUD + execute + interrupt endpoints
│   │       │   ├── campaigns.py       # Red-team campaign endpoints
│   │       │   ├── finetune.py        # Fine-tuning job endpoints
│   │       │   ├── skills.py          # Skill CRUD endpoints
│   │       │   ├── sandbox.py         # Sandbox execution endpoints
│   │       │   ├── stream.py          # SSE streaming endpoint
│   │       │   └── auth.py            # Auth endpoints
│   │       ├── middleware/
│   │       │   ├── error_handler.py
│   │       │   └── rate_limiter.py
│   │       └── schemas/               # Pydantic request/response schemas
│   │           ├── agent_schemas.py
│   │           ├── campaign_schemas.py
│   │           ├── finetune_schemas.py
│   │           └── skill_schemas.py
│   │
│   ├── migrations/                # Alembic migrations
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic.ini
│
├── frontend/
│   ├── src/
│   │   ├── app/                   # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx           # Landing / Dashboard
│   │   │   ├── agents/
│   │   │   │   ├── page.tsx       # Agent list
│   │   │   │   ├── [id]/
│   │   │   │   │   ├── page.tsx   # Agent detail
│   │   │   │   │   ├── builder/page.tsx    # Visual graph builder
│   │   │   │   │   ├── execute/page.tsx    # Execution monitor
│   │   │   │   │   └── security/page.tsx   # Red-team dashboard
│   │   │   │   └── new/page.tsx   # Create agent wizard
│   │   │   ├── campaigns/
│   │   │   │   ├── page.tsx       # Campaign list
│   │   │   │   └── [id]/page.tsx  # Campaign report detail
│   │   │   ├── finetune/
│   │   │   │   ├── page.tsx       # Fine-tune jobs list
│   │   │   │   └── new/page.tsx   # Launch fine-tune wizard
│   │   │   ├── skills/
│   │   │   │   ├── page.tsx       # Skill marketplace
│   │   │   │   └── new/page.tsx   # Create skill
│   │   │   ├── sandbox/
│   │   │   │   └── page.tsx       # Sandbox playground
│   │   │   └── settings/
│   │   │       └── page.tsx
│   │   ├── components/
│   │   │   ├── agent-builder/
│   │   │   │   ├── AgentCanvas.tsx        # React Flow canvas
│   │   │   │   ├── NodePalette.tsx        # Draggable node types
│   │   │   │   ├── NodeConfigPanel.tsx    # Node properties sidebar
│   │   │   │   ├── nodes/
│   │   │   │   │   ├── LLMNode.tsx
│   │   │   │   │   ├── ToolNode.tsx
│   │   │   │   │   ├── SubAgentNode.tsx
│   │   │   │   │   ├── ConditionalNode.tsx
│   │   │   │   │   └── HumanApprovalNode.tsx
│   │   │   │   └── edges/
│   │   │   │       └── ConditionalEdge.tsx
│   │   │   ├── redteam/
│   │   │   │   ├── SecurityScoreCard.tsx
│   │   │   │   ├── VulnerabilityChart.tsx
│   │   │   │   ├── AttackResultTable.tsx
│   │   │   │   └── CampaignTimeline.tsx
│   │   │   ├── execution/
│   │   │   │   ├── ExecutionLog.tsx        # Real-time SSE log viewer
│   │   │   │   ├── InterruptModal.tsx      # Approve/Reject/Edit modal
│   │   │   │   └── AgentStateViewer.tsx    # Current agent state tree
│   │   │   ├── finetune/
│   │   │   │   ├── TrainingProgress.tsx
│   │   │   │   ├── HyperparamForm.tsx
│   │   │   │   └── DatasetUploader.tsx
│   │   │   └── ui/                        # shadcn/ui components
│   │   ├── lib/
│   │   │   ├── api.ts             # API client (fetch wrapper)
│   │   │   ├── sse.ts             # SSE connection manager
│   │   │   ├── stores/            # Zustand stores
│   │   │   └── utils.ts
│   │   └── types/
│   │       └── index.ts           # Shared TypeScript types
│   ├── public/
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── modal_functions/               # Modal serverless functions
│   ├── train.py                   # Unsloth fine-tuning function
│   ├── inference.py               # Model inference endpoint
│   └── sandbox.py                 # Sandbox container function
│
├── promptfoo_templates/           # Promptfoo config templates
│   ├── base.yaml                  # Base red-team config
│   ├── owasp_llm.yaml            # OWASP LLM Top 10 preset
│   ├── nist_ai.yaml              # NIST AI RMF preset
│   └── custom_policies/
│       ├── legal_agent.yaml
│       └── customer_support.yaml
│
├── skills/                        # Built-in skills
│   ├── registry.json              # Skill registry
│   ├── web_search/
│   │   ├── SKILL.md
│   │   └── tool.py
│   ├── rag_retrieval/
│   │   ├── SKILL.md
│   │   └── tool.py
│   └── code_execution/
│       ├── SKILL.md
│       └── tool.py
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
├── README.md
├── PROJECT.md                     # GSD project spec
├── REQUIREMENTS.md                # GSD requirements
└── CLAUDE.md                      # Claude Code instructions
```

### 3.2 Diagramme de Flux — Cycle de Vie Complet

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AGENTFORGE PLATFORM                                │
│                                                                              │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │   BUILDER    │───▶│   SANDBOX    │───▶│  RED-TEAM    │───▶│  DEPLOY    │  │
│  │  (Design)    │    │   (Test)     │    │  (Secure)    │    │ (Ship)     │  │
│  └─────────────┘    └──────────────┘    └──────────────┘    └────────────┘  │
│        │                   │                   │                   │         │
│        ▼                   ▼                   ▼                   ▼         │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │  LangGraph   │    │ Modal/Docker │    │  Promptfoo   │    │  Modal     │  │
│  │  Deep Agents │    │  Isolated    │    │  50+ plugins │    │  Endpoint  │  │
│  │  React Flow  │    │  Container   │    │  OWASP/NIST  │    │  or API    │  │
│  └─────────────┘    └──────────────┘    └──────────────┘    └────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    FINE-TUNING PIPELINE                                  │ │
│  │   Dataset Upload ──▶ Unsloth QLoRA ──▶ Modal GPU ──▶ Deploy Endpoint   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    CROSS-CUTTING CONCERNS                               │ │
│  │   Human-in-the-Loop │ SSE Streaming │ Redis State │ Langfuse Tracing   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Modèle de Données (PostgreSQL)

### Tables Principales

```sql
-- Users & Auth
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agents
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    graph_definition JSONB NOT NULL,       -- LangGraph graph structure
    model_config JSONB NOT NULL,           -- Model provider, temperature, etc.
    interrupt_config JSONB DEFAULT '{}',   -- Tool-level interrupt settings
    skills TEXT[] DEFAULT '{}',            -- Attached skill IDs
    status VARCHAR(20) DEFAULT 'draft',    -- draft | active | archived
    security_score FLOAT,                  -- Latest red-team score (0-100)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent Executions
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    thread_id VARCHAR(255) NOT NULL,       -- LangGraph thread ID
    status VARCHAR(20) DEFAULT 'running',  -- running | paused | completed | failed
    input_messages JSONB NOT NULL,
    output_messages JSONB,
    interrupt_state JSONB,                 -- Pending interrupt data
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    token_usage JSONB,                     -- {input_tokens, output_tokens, cost}
    duration_ms INTEGER
);

-- Red-Team Campaigns
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    config JSONB NOT NULL,                 -- Promptfoo config
    status VARCHAR(20) DEFAULT 'pending',  -- pending | running | completed | failed
    overall_score FLOAT,                   -- 0-100 security score
    total_tests INTEGER,
    passed_tests INTEGER,
    failed_tests INTEGER,
    report JSONB,                          -- Full promptfoo report
    vulnerabilities JSONB,                 -- Breakdown by category
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skills
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',
    source_code TEXT NOT NULL,             -- Python source
    parameters_schema JSONB,              -- JSON Schema for tool params
    permissions TEXT[] DEFAULT '{}',       -- read | write | execute | network
    is_public BOOLEAN DEFAULT false,
    security_validated BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fine-Tune Jobs
CREATE TABLE finetune_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    base_model VARCHAR(255) NOT NULL,      -- e.g. "Qwen/Qwen2.5-7B"
    dataset_path VARCHAR(500) NOT NULL,
    hyperparams JSONB NOT NULL,            -- {lora_rank, lora_alpha, epochs, lr, ...}
    status VARCHAR(20) DEFAULT 'pending',  -- pending | training | completed | failed
    modal_job_id VARCHAR(255),             -- Modal function call ID
    metrics JSONB,                         -- {loss, eval_loss, perplexity, ...}
    model_output_path VARCHAR(500),        -- Path to fine-tuned weights
    inference_endpoint VARCHAR(500),       -- Modal inference URL
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vector store for RAG (pgvector)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1536),                -- OpenAI ada-002 dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## 5. API Contract (FastAPI Endpoints)

### 5.1 Agents

```
POST   /api/v1/agents                    # Create agent
GET    /api/v1/agents                    # List user's agents
GET    /api/v1/agents/{id}               # Get agent detail
PUT    /api/v1/agents/{id}               # Update agent config
DELETE /api/v1/agents/{id}               # Delete agent

POST   /api/v1/agents/{id}/execute       # Start execution
GET    /api/v1/agents/{id}/executions    # List executions
GET    /api/v1/agents/{id}/executions/{exec_id}  # Get execution detail

POST   /api/v1/agents/{id}/executions/{exec_id}/interrupt
       Body: { "decisions": [{"type": "approve"}, {"type": "reject"}] }
       # Resume from interrupt with human decisions

GET    /api/v1/agents/{id}/stream/{exec_id}   # SSE stream (execution logs)
```

### 5.2 Red-Team Campaigns

```
POST   /api/v1/campaigns                 # Launch campaign for an agent
GET    /api/v1/campaigns                 # List campaigns
GET    /api/v1/campaigns/{id}            # Get campaign detail + report
GET    /api/v1/campaigns/{id}/report     # Download full report (JSON/PDF)
DELETE /api/v1/campaigns/{id}            # Delete campaign
```

### 5.3 Fine-Tuning

```
POST   /api/v1/finetune                  # Launch fine-tune job
GET    /api/v1/finetune                  # List jobs
GET    /api/v1/finetune/{id}             # Get job status + metrics
POST   /api/v1/finetune/{id}/deploy      # Deploy model as inference endpoint
DELETE /api/v1/finetune/{id}             # Cancel/delete job
```

### 5.4 Skills

```
POST   /api/v1/skills                    # Create skill
GET    /api/v1/skills                    # List skills (public + user's)
GET    /api/v1/skills/{id}               # Get skill detail
PUT    /api/v1/skills/{id}               # Update skill
DELETE /api/v1/skills/{id}               # Delete skill
POST   /api/v1/skills/{id}/validate      # Run security validation
```

### 5.5 Sandbox

```
POST   /api/v1/sandbox/run               # Execute code/agent in sandbox
GET    /api/v1/sandbox/stream/{id}       # SSE stream sandbox output
```

### 5.6 Auth

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login                # Returns JWT
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me
```

---

## 6. Composants Clés — Implémentation Détaillée

### 6.1 LangGraph Agent Orchestrator

```python
# backend/app/infrastructure/orchestration/langgraph_orchestrator.py

"""
Ce module traduit la graph_definition JSON (créée par le builder frontend)
en un graphe LangGraph exécutable.

La graph_definition JSON a cette structure :
{
  "nodes": [
    {"id": "classifier", "type": "llm", "config": {"model": "gpt-5.4-mini", "prompt": "..."}},
    {"id": "extractor", "type": "tool", "config": {"tool_name": "rag_retrieval"}},
    {"id": "validator", "type": "subagent", "config": {"system_prompt": "..."}},
    {"id": "human_check", "type": "interrupt", "config": {"allowed_decisions": ["approve", "reject"]}}
  ],
  "edges": [
    {"from": "classifier", "to": "extractor", "condition": null},
    {"from": "extractor", "to": "human_check", "condition": null},
    {"from": "human_check", "to": "validator", "condition": "approved"}
  ],
  "entry_point": "classifier"
}

Chaque type de node est mappé :
- "llm"       → LLM call node (ChatModel.invoke)
- "tool"      → Tool execution node (skill ou built-in)
- "subagent"  → Deep Agent sub-agent spawn (create_deep_agent)
- "interrupt"  → Human-in-the-loop pause (LangGraph interrupt)
- "conditional" → Routing conditionnel

L'orchestrateur :
1. Parse la definition JSON
2. Crée un StateGraph LangGraph
3. Ajoute les nodes et edges
4. Configure le checkpointer Redis
5. Compile le graphe
6. Expose invoke() et stream()
"""
```

### 6.2 Promptfoo Integration

```python
# backend/app/infrastructure/redteam/promptfoo_adapter.py

"""
Ce module génère dynamiquement une configuration promptfoo YAML
à partir de la configuration d'un agent, puis exécute les tests.

Workflow :
1. Lire la config de l'agent (graph_definition, model_config, skills)
2. Générer automatiquement :
   - purpose : description de ce que fait l'agent
   - targets : endpoint HTTP pointant vers l'agent (ou callable Python)
   - plugins : sélection automatique basée sur les outils/skills attachés
     - Si l'agent a accès au filesystem → ajouter shell-injection, path-traversal
     - Si l'agent fait du RAG → ajouter rag-document-exfiltration, rag-poisoning
     - Si l'agent a des tools API → ajouter ssrf, bfla, bola
     - Toujours inclure : prompt-injection, jailbreak, harmful, hijacking, pii
   - strategies : jailbreak, prompt-injection, multilingual
3. Écrire le fichier YAML temporaire
4. Exécuter `promptfoo redteam generate` puis `promptfoo eval`
5. Parser le JSON de résultat
6. Calculer le score de sécurité et persister dans la DB

Le score de sécurité est calculé :
  security_score = (passed_tests / total_tests) * 100

Les vulnérabilités sont groupées par catégorie avec severity (critical/high/medium/low).
"""
```

### 6.3 Modal Fine-Tuning Function

```python
# modal_functions/train.py

"""
Fonction Modal serverless pour le fine-tuning avec Unsloth.

@app.function(
    gpu="A10G",  # ou "A100" pour modèles >7B
    timeout=3600,
    image=modal.Image.debian_slim(python_version="3.12")
        .pip_install("unsloth", "transformers", "datasets", "trl", "peft", "bitsandbytes")
    volumes={"/data": volume}  # Volume persistant pour modèles/datasets
)
def train(config: dict) -> dict:
    '''
    config = {
        "base_model": "unsloth/Qwen2.5-7B-bnb-4bit",
        "dataset_path": "/data/datasets/my_dataset.jsonl",
        "lora_rank": 16,
        "lora_alpha": 32,
        "num_epochs": 3,
        "learning_rate": 2e-4,
        "max_seq_length": 2048,
        "output_dir": "/data/models/my_finetuned"
    }

    Steps :
    1. Load base model with Unsloth (FastLanguageModel.from_pretrained)
    2. Apply LoRA (get_peft_model)
    3. Load & format dataset
    4. Train with SFTTrainer (ou DPOTrainer si DPO)
    5. Save model + tokenizer
    6. Return metrics {loss, eval_loss, training_time, gpu_memory_used}
    '''
```

### 6.4 Human-in-the-Loop Middleware

```python
# backend/app/infrastructure/orchestration/middleware/interrupt_handler.py

"""
Middleware LangGraph pour le human-in-the-loop.

Utilise le pattern Deep Agents d'interrupts :
- Chaque tool peut être marqué comme "interruptible" dans la config
- Quand un tool interruptible est appelé, le graphe LangGraph pause
- L'état est persisté dans Redis (checkpointer)
- L'API envoie un event SSE au frontend : {"type": "interrupt", "data": {...}}
- Le frontend affiche le modal InterruptModal
- L'utilisateur approve/reject/edit
- L'API envoie Command(resume={"decisions": [...]})
- Le graphe reprend

Config format dans interrupt_config :
{
    "delete_file": {"allowed_decisions": ["approve", "reject"]},
    "send_email": {"allowed_decisions": ["approve", "edit", "reject"]},
    "execute_code": true,  # Default: all decisions allowed
    "web_search": false    # No interrupt needed
}
"""
```

### 6.5 SSE Streaming

```python
# backend/app/api/v1/stream.py

"""
Endpoint SSE pour le streaming en temps réel des exécutions d'agents.

GET /api/v1/agents/{agent_id}/stream/{execution_id}

Events types :
- agent_start      : {"agent_name": "classifier", "input": {...}}
- agent_end        : {"agent_name": "classifier", "output": {...}, "duration_ms": 234}
- tool_call        : {"tool_name": "rag_retrieval", "args": {...}}
- tool_result      : {"tool_name": "rag_retrieval", "result": {...}}
- interrupt        : {"action_requests": [...], "review_configs": [...]}
- token            : {"content": "partial response text..."}  # Streaming tokens
- subagent_spawn   : {"subagent_name": "researcher", "task": "..."}
- error            : {"message": "...", "traceback": "..."}
- complete         : {"total_duration_ms": 1234, "total_tokens": 567}

Implémenté via Redis Pub/Sub :
- L'orchestrateur publie les events sur le channel execution:{exec_id}
- Le endpoint SSE s'abonne et forward au client
"""
```

---

## 7. User Stories Prioritaires

### P0 — MVP (Phase 1-3)

```
US-001: En tant qu'utilisateur, je peux créer un agent simple (1 noeud LLM + 1 tool)
        via une interface web et le tester dans la sandbox.
        Critères : L'agent s'exécute, produit une réponse, les logs sont visibles en temps réel.

US-002: En tant qu'utilisateur, je peux lancer une campagne de red-teaming sur mon agent
        et voir un rapport avec score de sécurité et vulnérabilités détectées.
        Critères : Au moins 10 types de tests, score 0-100, breakdown par catégorie.

US-003: En tant qu'utilisateur, je peux voir les logs d'exécution de mon agent en temps réel
        (streaming SSE) avec les prompts, réponses, et appels d'outils.
        Critères : Latence < 200ms entre l'event et l'affichage.
```

### P1 — Core Features (Phase 4-5)

```
US-004: En tant qu'utilisateur, je peux configurer des interrupts sur des outils spécifiques
        et approuver/refuser/modifier les actions de l'agent via un modal.
        Critères : L'exécution pause, le modal s'affiche, la décision reprend le workflow.

US-005: En tant qu'utilisateur, je peux créer un pipeline multi-agents (supervisor + sous-agents)
        via le builder visuel drag-and-drop.
        Critères : Au moins 3 noeuds, edges conditionnels, preview du graphe.

US-006: En tant qu'utilisateur, je peux lancer un fine-tuning QLoRA sur un modèle
        via l'interface, suivre la progression, et déployer le modèle comme endpoint.
        Critères : Choix du modèle base, upload dataset, monitoring loss, deploy en 1 clic.

US-007: En tant qu'utilisateur, je peux créer une skill (outil Python) et la tester
        dans la sandbox avant de l'attacher à un agent.
        Critères : Éditeur de code, exécution sandbox, validation sécurité automatique.
```

### P2 — Advanced (Phase 6-8)

```
US-008: En tant qu'utilisateur, je peux comparer les scores de sécurité entre
        différentes versions de mon agent (avant/après modification de prompt).

US-009: En tant qu'utilisateur, je peux exporter mon agent comme template
        et l'importer dans un autre projet.

US-010: En tant qu'utilisateur, je peux configurer des campagnes red-team
        automatiques en CI/CD (à chaque merge sur main).
```

---

## 8. Configuration Docker Compose (Dev)

```yaml
# docker-compose.yml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://forge:forge@db:5432/agentforge
      - REDIS_URL=redis://redis:6379/0
      - MODAL_TOKEN_ID=${MODAL_TOKEN_ID}
      - MODAL_TOKEN_SECRET=${MODAL_TOKEN_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev

  db:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_USER=forge
      - POSTGRES_PASSWORD=forge
      - POSTGRES_DB=agentforge
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

---

## 9. Instructions pour l'Agent de Développement

### Principes de Code

```markdown
## RÈGLES ABSOLUES

1. **Clean Architecture stricte** : Les dépendances pointent TOUJOURS vers l'intérieur
   (API → Application → Domain). Le domain ne connaît PAS l'infrastructure.

2. **Ports & Adapters** : Toute dépendance externe (DB, Redis, Modal, promptfoo)
   est abstraite par un Port (ABC) dans le domain, implémentée par un Adapter
   dans infrastructure.

3. **Pydantic everywhere** : Chaque input/output d'API est un Pydantic model.
   Chaque config est un BaseSettings. Zero dict non typé.

4. **Async first** : Toutes les routes FastAPI sont async.
   SQLAlchemy utilise AsyncSession. Redis utilise aioredis.

5. **Tests** : Chaque use case a un test unitaire. Chaque endpoint a un test
   d'intégration. Coverage minimum 80%.

6. **Error handling** : Exceptions custom par domaine (AgentNotFound,
   CampaignFailed, TrainingError). Middleware global de gestion d'erreurs.

7. **Logging** : structlog partout. Chaque opération significative est loggée
   avec correlation_id.

8. **Git** : Atomic commits. Un commit = une tâche GSD. Message format :
   "feat(agent-builder): implement LangGraph graph compilation"
```

### Patterns de Code

```python
# PATTERN 1 : Use Case (Command)
# backend/app/application/commands/create_agent.py
from dataclasses import dataclass
from app.domain.ports.agent_repository import AgentRepository

@dataclass
class CreateAgentCommand:
    user_id: str
    name: str
    description: str
    graph_definition: dict
    model_config: dict

class CreateAgentHandler:
    def __init__(self, repo: AgentRepository):
        self._repo = repo

    async def handle(self, cmd: CreateAgentCommand) -> Agent:
        agent = Agent.create(
            user_id=cmd.user_id,
            name=cmd.name,
            description=cmd.description,
            graph_definition=cmd.graph_definition,
            model_config=cmd.model_config,
        )
        await self._repo.save(agent)
        return agent


# PATTERN 2 : Port (Interface)
# backend/app/domain/ports/redteam_engine.py
from abc import ABC, abstractmethod

class RedTeamEngine(ABC):
    @abstractmethod
    async def generate_config(self, agent: Agent) -> dict:
        """Generate promptfoo config from agent definition."""

    @abstractmethod
    async def run_campaign(self, config: dict) -> CampaignReport:
        """Execute red-team campaign and return report."""


# PATTERN 3 : Adapter (Implementation)
# backend/app/infrastructure/redteam/promptfoo_adapter.py
class PromptfooAdapter(RedTeamEngine):
    async def generate_config(self, agent: Agent) -> dict:
        # ... generate YAML config
        pass

    async def run_campaign(self, config: dict) -> CampaignReport:
        # ... execute promptfoo CLI, parse results
        pass


# PATTERN 4 : FastAPI Route with DI
# backend/app/api/v1/campaigns.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

@router.post("/", response_model=CampaignResponse)
async def launch_campaign(
    body: LaunchCampaignRequest,
    service: RedTeamService = Depends(get_redteam_service),
):
    campaign = await service.launch(
        agent_id=body.agent_id,
        plugins=body.plugins,
        strategies=body.strategies,
    )
    return CampaignResponse.from_entity(campaign)
```

### Ordre de Build Recommandé

```markdown
## SÉQUENCE DE DÉVELOPPEMENT

### Sprint 1 : Foundation (Semaine 1-2)
- [ ] Setup monorepo, Docker Compose, CI/CD GitHub Actions
- [ ] Backend : FastAPI skeleton, config, DB models, Alembic migrations
- [ ] Frontend : Next.js skeleton, Tailwind, shadcn/ui, routing
- [ ] Auth : JWT register/login/me

### Sprint 2 : Agent Core (Semaine 3-4)
- [ ] Domain : Agent entity, AgentRepository port
- [ ] Infrastructure : PostgreSQL adapter, LangGraph orchestrator
- [ ] API : CRUD agents, execute agent (simple 1-node)
- [ ] Frontend : Agent list page, create agent form
- [ ] SSE : Redis pub/sub + SSE endpoint + frontend log viewer

### Sprint 3 : Builder & Sandbox (Semaine 5-6)
- [ ] Frontend : React Flow canvas, node palette, config panel
- [ ] Backend : Parse graph_definition → LangGraph compilation
- [ ] Sandbox : Docker-based isolated execution
- [ ] Skills : CRUD, registry, loader, sandbox test

### Sprint 4 : Red-Team Engine (Semaine 7-8)
- [ ] Infrastructure : Promptfoo adapter (config gen + execution + parsing)
- [ ] API : Campaign CRUD + launch + report
- [ ] Frontend : Security dashboard, score card, vulnerability chart
- [ ] Integration : Auto-campaign on agent update

### Sprint 5 : Human-in-the-Loop (Semaine 9)
- [ ] LangGraph interrupt middleware
- [ ] SSE interrupt events
- [ ] Frontend : InterruptModal (approve/reject/edit)
- [ ] Config : Per-tool interrupt settings in builder

### Sprint 6 : Fine-Tuning (Semaine 10-11)
- [ ] Modal functions : train.py (Unsloth QLoRA)
- [ ] Modal functions : inference.py (deploy endpoint)
- [ ] API : FineTune CRUD + launch + deploy
- [ ] Frontend : Training wizard, progress monitor, deploy button

### Sprint 7 : Polish & Deploy (Semaine 12)
- [ ] E2E tests (Playwright)
- [ ] Performance optimization
- [ ] Documentation (README, API docs, user guide)
- [ ] Docker prod config, deploy
```

---

## 10. Métriques de Succès du Projet

| Métrique | Target |
|---|---|
| Temps de création d'un agent (builder → exécution) | < 5 min |
| Temps d'une campagne red-team (50 tests) | < 10 min |
| Latence SSE (event → affichage) | < 200ms |
| Score de sécurité d'un agent bien configuré | > 85/100 |
| Temps de fine-tuning 7B model (1 epoch, 1K samples) | < 30 min |
| Coverage tests backend | > 80% |
| Lighthouse score frontend | > 90 |

---

## 11. Références & Ressources

| Ressource | URL |
|---|---|
| LangGraph Docs | https://docs.langchain.com/oss/python/langgraph/overview |
| Deep Agents SDK | https://docs.langchain.com/oss/python/deepagents/overview |
| Deep Agents HITL | https://docs.langchain.com/oss/python/deepagents/human-in-the-loop |
| Promptfoo Red-Team | https://www.promptfoo.dev/docs/red-team/ |
| Promptfoo Config | https://www.promptfoo.dev/docs/red-team/configuration/ |
| Unsloth GitHub | https://github.com/unslothai/unsloth |
| Modal Docs | https://modal.com/docs |
| GSD Framework | https://github.com/gsd-build/get-shit-done |
| React Flow | https://reactflow.dev/ |
| OWASP LLM Top 10 | https://owasp.org/www-project-top-10-for-large-language-model-applications/ |
| NIST AI RMF | https://www.nist.gov/artificial-intelligence/ai-risk-management-framework |

---

## 12. CLAUDE.md (Instructions pour Claude Code)

```markdown
# CLAUDE.md — AgentForge Project

## Project Overview
AgentForge is a full-stack platform for building, red-teaming, and deploying LLM agents.
Monorepo with Python FastAPI backend and Next.js frontend.

## Tech Stack
- Backend: Python 3.12, FastAPI, LangGraph, SQLAlchemy 2.0, Pydantic v2, Redis
- Frontend: Next.js 15, React 19, Tailwind CSS, shadcn/ui, React Flow, Recharts
- Infrastructure: PostgreSQL 16 + pgvector, Redis, Docker, Modal (GPU)
- Testing: pytest, Vitest, Playwright

## Architecture Rules
- Clean Architecture: domain/ has ZERO external dependencies
- All external services accessed through Ports (ABC) → Adapters
- Async everywhere (FastAPI, SQLAlchemy AsyncSession, aioredis)
- Pydantic v2 for ALL schemas, configs, and validation

## Code Style
- Python: Ruff formatting, type hints mandatory, docstrings on public methods
- TypeScript: ESLint + Prettier, strict mode, no `any`
- Git: atomic commits, conventional commits format

## Key Directories
- backend/app/domain/ — Business logic, entities, ports (NEVER import infrastructure here)
- backend/app/application/ — Use cases (commands/queries)
- backend/app/infrastructure/ — External adapters (DB, Redis, Modal, promptfoo)
- backend/app/api/ — FastAPI routes
- frontend/src/app/ — Next.js pages
- frontend/src/components/ — React components
- modal_functions/ — Modal serverless GPU functions

## Running Locally
docker compose up -d
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev

## Testing
cd backend && pytest
cd frontend && npm test
```

---

*Ce prompt est conçu pour être injecté tel quel dans un agent de développement. Il contient toutes les informations nécessaires pour construire AgentForge de A à Z sans ambiguïté.*
