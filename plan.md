# AgentForge — Analyse stratégique & Roadmap future

---

## TL;DR — Point d'originalité

**AgentForge est le seul agent platform qui ferme la boucle : design → sécurité → fine-tuning → gouvernance en self-hosted.**

Ni LangChain (bibliothèque), ni Agno (SaaS cloud), mais un **système d'exploitation pour agents** : versionnable, auditable, testable automatiquement, fine-tunable sur ses propres traces de production.

---

## 1. Analyse de l'existant

### Forces solides

| Domaine | Ce qui existe | Qualité |
|---|---|---|
| Architecture | Clean Architecture DDD, ports & adapters, frozen dataclasses | ★★★★★ |
| Portabilité | Agents = JSON, SDK local (validate/run/pull/push/eval) | ★★★★☆ |
| Sécurité | ExecutionPolicy, sandbox subprocess, deny_patterns, HITL, skill AST validation | ★★★★☆ |
| Observabilité | Langfuse + LangSmith + Sentry + structured logging + correlation ID | ★★★★☆ |
| Red-team | Mock engine (12 vecteurs) + promptfoo, CI baseline persistence | ★★★★☆ |
| Versionning | Snapshots auto, diff, rollback, stats par version | ★★★★☆ |
| Visual builder | React Flow graph editor, tous node types | ★★★★☆ |
| Fine-tuning | Pipeline Modal GPU complet, live dashboard | ★★★☆☆ |
| HITL | Interrupt LangGraph, modal UI, PostgreSQL checkpointer | ★★★★☆ |
| RAG | pgvector, document upload, semantic search | ★★★☆☆ |

### Gaps critiques identifiés

- **SDK trop thin** : pas de type system Python riche, pas de TS/JS SDK, pas de streaming, subagent/interrupt non supportés localement
- **Orchestrateur = LangGraph** : couplage fort, pas de parallélisme de nœuds exposé, pas de node types extensibles
- **Mémoire absente** : pas de mémoire persistante cross-sessions (court/long terme)
- **Pas de registry public** : skills non partageables, pas de marketplace
- **Outil résultat non typé** : tool output = string seulement
- **Coût invisible** : pas de cost tracking par exécution, pas de budget enforcement
- **Multi-modal absent** : images, fichiers non supportés comme input agent
- **Triggers externes absents** : pas de webhooks, pas de schedules, pas d'intégrations (Slack, GitHub, etc.)

---

## 2. Positionnement vs compétiteurs

### LangChain / LangGraph
- **Force** : Ecosystem énorme, LCEL, LangGraph très mature, communauté
- **Faiblesse** : Complexité maximale, pas de plateforme, pas de gouvernance, pas de red-team built-in, code-only
- **AgentForge différence** : plateforme complète avec lifecycle (build → test → govern → improve), SDK portable, visual builder no-code

### Agno (ex-Phidata)
- **Force** : Python-native, agent teams, structured outputs, SDK clean, cloud hosting
- **Faiblesse** : SaaS potentiel vendor lock-in, pas de fine-tuning loop, pas de red-team intégré, gouvernance limitée
- **AgentForge différence** : **100% self-hosted**, boucle fine-tuning sur ses propres traces, red-team CI, execution policy enterprise

### CrewAI
- **Force** : Multi-agent collaboratif, rôles, tasks, facilité usage
- **Faiblesse** : Pas de visual builder, pas de versioning, pas de sécurité avancée
- **AgentForge différence** : Visual-first, versions + rollback, security-first

### AutoGen (Microsoft)
- **Force** : Multi-agent conversations, humain dans la boucle
- **Faiblesse** : Recherche académique, pas production-ready, complexe à déployer
- **AgentForge différence** : Production-ready, clean architecture, Docker, CI/CD intégré

### Combinaison unique d'AgentForge

```
Le seul agent platform qui combine dans un seul self-hosted system :
  1. Visual builder no-code → portabilité JSON
  2. Execution policy granulaire (tool allowlist, regex deny, HITL, URL scope)
  3. Red-team automatisé intégré au CI (12 vecteurs, baseline tracking)
  4. Fine-tuning loop sur les traces de production (Modal GPU)
  5. Versionning + rollback 1-click avec diff visuel
  6. Subagent delegation avec détection de cycles
```

---

## 3. Roadmap future — 6 phases

### Phase 1 — SDK Ecosystem 2.0 (priorité haute)

**Objectif** : Faire du SDK un citoyen de première classe, comparable à Vercel AI SDK ou LangChain JS.

**1.1 — SDK Python riche**
- Builder API fluent : `Agent().llm_node(...).tool_node(...).edge(...)` → export JSON ou exécution directe
- Type system complet : `AgentDefinition`, `NodeConfig`, `SkillSpec`, `PolicyConfig` comme Pydantic models exportables
- Support streaming dans SDK (async generator qui yield les events)
- Subagent + interrupt supportés localement (mock resolver configurable)
- Plugin system : `@agentforge.node("my_type")` pour ajouter des node types custom
- Fichiers cibles : `sdk/src/agentforge/builder.py`, `sdk/src/agentforge/types.py`, `sdk/src/agentforge/stream.py`

**1.2 — TypeScript/JS SDK**
- `@agentforge/sdk` sur npm
- Types auto-générés depuis OpenAPI spec backend
- `LocalAgent` équivalent en TS (LangChain.js + LangGraph.js)
- CLI : `npx agentforge validate/run/pull/push/eval`
- Nouveau dossier : `sdk-js/`

**1.3 — OpenAPI client auto-généré**
- `openapi-generator` → `sdk/src/agentforge/client/` (Python async)
- Remplace les `urllib.request` manuels dans `sdk/src/agentforge/cli.py`
- Authentification centralisée (token + refresh)

**1.4 — SDK Observability**
- Emitter local (stdout/JSON) dans le SDK
- Support OpenTelemetry en local
- `agentforge run --trace` → fichier de trace JSON

---

### Phase 2 — Runtime Overhaul : Orchestrateur découpable (priorité haute)

**Objectif** : Réduire le couplage à LangGraph, rendre l'orchestrateur extensible.

**2.1 — Runtime abstrait extensible**
- Créer `AgentRuntime` protocol : `build_graph(definition) -> CompiledGraph`
- `LangGraphRuntime` : implémentation actuelle (non-breaking)
- `NativeRuntime` : state machine sans LangGraph pour graphs simples
- Parallélisme de nœuds : `parallel_nodes: list[str]` dans GraphDefinition → fan-out/fan-in
- Fichiers : `backend/app/domain/ports/agent_runtime.py`, `backend/app/infrastructure/orchestration/native_runtime.py`

**2.2 — Custom Node Types (plugin system)**
- `NodeType` enum → extensible registry
- Nodes additionnels : `code_interpreter`, `file_reader`, `http_webhook`, `scheduled_trigger`, `memory_recall`
- Enregistrement via decorator : `@node_registry.register("code_interpreter")`
- Fichiers : `backend/app/domain/node_registry.py`, `backend/app/infrastructure/orchestration/node_plugins/`

**2.3 — Graph Debugger**
- Breakpoint sur un node_id (interrupt avant exécution)
- Step-by-step execution via API
- Inspection de l'état courant : messages, node actif, variables
- Replay d'une exécution passée
- Endpoint : `POST /agents/{id}/debug-session`

**2.4 — Cost tracking & Budget enforcement**
- Token counting par node + par exécution (`token_usage` déjà dans Execution entity)
- Estimation de coût en USD (tables pricing OpenAI + Google + Anthropic)
- `max_cost_usd` dans ExecutionPolicy → arrêt si dépassement
- Dashboard : coût total par agent, par version, par user
- Fichiers : `backend/app/domain/cost_tracker.py`, `backend/app/infrastructure/orchestration/cost_meter.py`

---

### Phase 3 — Memory & Context Management (priorité moyenne)

**Objectif** : Agents capables de se souvenir entre sessions.

**3.1 — Short-term memory (within session)**
- Compression automatique du contexte quand > N tokens (résumé LLM)
- Sliding window configurable dans ExecutionPolicy
- Fichier : `backend/app/infrastructure/orchestration/context_manager.py`

**3.2 — Long-term memory (cross-session)**
- `MemoryStore` port : `save(agent_id, user_id, key, value)`, `recall(agent_id, user_id, query, top_k)`
- Implémentation : pgvector (réutilise KnowledgeRepository)
- Node type `memory_recall` : query sémantique → inject dans contexte
- Node type `memory_save` : extract & stocker depuis output LLM
- Fichiers : `backend/app/domain/ports/memory_store.py`, `backend/app/infrastructure/memory/`

**3.3 — Persistent Agent State**
- `session_variables` dict dans Execution entity (clé-valeur typée)
- Template interpolation dans system_prompt + tool input : `{{variables.customer_name}}`
- Fichier : `backend/app/infrastructure/orchestration/template_engine.py`

---

### Phase 4 — Skills Marketplace & OSS Community (priorité moyenne)

**Objectif** : Faire d'AgentForge un hub open-source de skills partageables.

**4.1 — Public Skill Registry**
- `is_public` déjà dans `Skill` entity → exposer via API publique non-authée
- `GET /api/v1/skills/registry?search=...` endpoint
- Rating, downloads count, author
- Fichier : `backend/app/api/v1/registry.py`

**4.2 — Skill Packaging (AgentForge Package = AFP)**
- Format `skill.afp` : ZIP avec `manifest.json` + `skill.py` + `tests/` + `README.md`
- `agentforge skill publish` → upload au registry
- `agentforge skill install <name>@<version>` → installe dans workspace
- Dépendances inter-skills dans manifest
- Fichier : `sdk/src/agentforge/skill_pack.py`

**4.3 — Agent Templates / Blueprints**
- Agents préconfigurés publics (Support Triage Bot, Code Review Bot, Data Analyst, etc.)
- `agentforge init --template support-bot` → crée un projet complet
- `GET /api/v1/templates` endpoint
- Étend le pattern existant de `backend/app/domain/skill_templates.py`

**4.4 — Signed Skills**
- SHA256 déjà dans export → ajouter signature Ed25519 par auteur
- Verification côté SDK + backend avant exécution
- `security_score` par skill dans le registry public
- Fichier : `sdk/src/agentforge/signing.py`

---

### Phase 5 — Multi-modal & Integrations (priorité moyenne)

**Objectif** : Agents capables de traiter images, fichiers et de s'intégrer dans les workflows existants.

**5.1 — Multi-modal inputs**
- Node type `vision` : image → LLM vision (GPT-4V, Claude 3, Gemini Vision)
- Node type `file_reader` : PDF, CSV, DOCX → text extraction → inject dans contexte
- `MessageDict` → extend avec `content: str | list[ContentPart]`
- Fichiers : `backend/app/domain/value_objects.py`, `backend/app/infrastructure/orchestration/multimodal_handler.py`

**5.2 — MCP Protocol Support**
- `MCPSkill` type : wrap un MCP server comme skill
- `agentforge mcp add <server-url>` → register MCP server
- Auto-discovery des tools exposés
- Compatible avec tout l'écosystème MCP (Anthropic, etc.)
- Fichier : `backend/app/infrastructure/orchestration/mcp_adapter.py`

**5.3 — Webhook Triggers & Scheduled Executions**
- `TriggerConfig` dans Agent : type (webhook, schedule, event), config
- `POST /agents/{id}/trigger/webhook` → retourne URL dédiée
- Cron scheduler (APScheduler) → exécution auto
- Webhook secret validation (HMAC)
- Fichiers : `backend/app/domain/trigger.py`, `backend/app/infrastructure/triggers/`

**5.4 — Native Integrations (Skill Templates)**
- Skill templates natifs : Slack, GitHub, Linear, Notion, Google Sheets
- OAuth2 flow pour secrets d'intégration
- JSON schema enforcement sur les tool outputs (structured outputs)

---

### Phase 6 — Governance & Enterprise (priorité basse mais stratégique)

**Objectif** : Enterprise-ready : audit, compliance, multi-tenant, SSO.

**6.1 — Audit Trail tamper-proof**
- Hash chain sur les Execution records
- Export audit CSV/JSON signé
- GDPR : anonymisation des messages, droit à l'oubli
- Fichier : `backend/app/infrastructure/audit/execution_audit.py`

**6.2 — Multi-tenant / Organizations**
- Organizations (tenants) au-dessus des Users
- RBAC : Owner, Admin, Developer, Viewer par organization
- Resource quotas par org (max agents, max executions/month, max cost/month)
- Fichiers : `backend/app/domain/entities/organization.py`

**6.3 — SSO / SAML / OIDC**
- Intégration SAML2 / OIDC pour login enterprise
- Fichier : `backend/app/infrastructure/auth/sso.py`

**6.4 — Compliance Dashboard**
- Vue agrégée : red-team scores historique, violations de policy, HITL usage
- Export rapport PDF pour audits

---

## 4. Propositions d'originalité technique forte

### A — "Policy as Code" (différenciateur #1)

ExecutionPolicy actuelle est YAML/JSON. Aller plus loin avec une fluent API dans le SDK :

```python
policy = AgentPolicy()
  .deny_tool("shell_exec", "network_call")
  .require_approval_for("send_email", "database_write")
  .deny_input_pattern(r"password|secret|token")
  .max_cost(0.50, currency="USD")
  .max_steps(100)
  .allow_fetch_only("https://api.company.com/*")
```

Export → JSON stocké dans agent. Import → enforcement automatique dans l'orchestrateur.

**Positionnement** : "OPA (Open Policy Agent) pour les agents LLM"

---

### B — "Trace-Driven Fine-tuning" (différenciateur #2)

La boucle unique qu'aucun framework n'a :

1. Exécutions → traces collectées (`token_usage`, messages, feedback score)
2. `POST /finetune` avec `from_executions: true, min_score: 0.8` → sélection auto des meilleurs exemples
3. Fine-tuning sur Modal GPU avec Unsloth LoRA
4. Déploiement → nouveau finetuned provider dans `AgentModelConfig`
5. A/B test : version N (GPT-4) vs version N+1 (finetuned) via `/stats/versions`

**Positionnement** : "Le premier agent platform qui apprend de sa propre production"

---

### C — "Security Score as a First-Class Citizen" (différenciateur #3)

`security_score` existe sur `Agent` entity. Aller plus loin :

- Score live recalculé après chaque red-team campaign
- Score par dimension : injection, data leakage, jailbreak, tool misuse
- Badge public pour agents open-sourcés (comme npm audit score)
- Policy de déploiement : `min_security_score: 0.8` → blocage si score insuffisant

**Positionnement** : "Le seul framework avec un security score natif dans la CI"

---

### D — "Graph as Universal Format" (différenciateur #4)

GraphDefinition JSON → exporter vers :
- Mermaid diagram (documentation auto-générée)
- LangChain LCEL (compatibilité descendante)
- OpenAI Assistants format
- Anthropic Agents format

Fichier : `sdk/src/agentforge/exporters/`

**Positionnement** : "Write once, run anywhere agents"

---

## 5. Ordre d'implémentation suggéré

```
Sprint 1 (1-2 semaines): Foundation
  - SDK builder API fluent (phase 1.1)
  - Cost tracking + budget enforcement (phase 2.4)
  - Memory court-terme avec compression (phase 3.1)

Sprint 2 (2-3 semaines): Ecosystem
  - TypeScript SDK minimal (phase 1.2)
  - Public skill registry + agent templates (phase 4.1 + 4.3)
  - Policy as Code SDK API (proposition A)

Sprint 3 (3-4 semaines): Runtime
  - Custom node types plugin system (phase 2.2)
  - MCP Protocol support (phase 5.2)
  - Memory long-terme cross-session (phase 3.2)

Sprint 4 (3-4 semaines): Enterprise loop
  - Trace-driven fine-tuning (proposition B)
  - Webhook triggers + schedules (phase 5.3)
  - Graph exporters Mermaid + LCEL (proposition D)

Sprint 5 (4-5 semaines): Governance
  - Multi-tenant / Organizations (phase 6.2)
  - Audit trail tamper-proof (phase 6.1)
  - SSO/SAML/OIDC (phase 6.3)
```

---

## 6. OSS Readiness Checklist

- [ ] `LICENSE` MIT à la racine (manquant actuellement)
- [ ] `CODE_OF_CONDUCT.md`
- [ ] `SECURITY.md` (responsible disclosure process)
- [ ] `.github/ISSUE_TEMPLATE/` (bug, feature request, security)
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] `CONTRIBUTING.md` entièrement en anglais
- [ ] Supprimer les hardcoded `"gpt-5.4-mini"` → config default
- [ ] Badges README : CI status, coverage, security score, PyPI version
- [ ] `sdk/` publié sur PyPI (`pip install agentforge-sdk`)
- [ ] `sdk-js/` publié sur npm (`npm install @agentforge/sdk`)
- [ ] Docs site (MkDocs/Docusaurus) avec quickstart + API reference
- [ ] `CHANGELOG.md`
- [ ] GitHub Discussions activé pour la communauté
- [ ] Community Discord

---

## 7. Fichiers critiques de référence

| Fichier | Pour quelle phase |
|---|---|
| `sdk/src/agentforge/agent.py` | Phase 1.1 : enrichir SDK builder |
| `sdk/src/agentforge/cli.py` | Phase 1.1 : streaming, MCP commands |
| `backend/app/domain/execution_policy.py` | Proposition A : Policy as Code |
| `backend/app/domain/graph_definition.py` | Proposition D : exporters, Phase 2.1 |
| `backend/app/infrastructure/orchestration/langgraph_orchestrator.py` | Phase 2.1 : runtime abstraction |
| `backend/app/domain/entities/skill.py` | Phase 4.1 : public registry |
| `backend/app/application/services/finetune_service.py` | Proposition B : trace-driven finetune |
| `backend/app/domain/skill_templates.py` | Phase 4.3 : agent templates |
| `backend/app/config.py` | Phase 2 : OBSERVABILITY_BACKEND, runtime config |
| `backend/app/api/v1/agents.py` | Phase 2.3 : debug session endpoint |
