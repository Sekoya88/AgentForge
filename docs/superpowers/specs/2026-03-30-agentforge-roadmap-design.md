# AgentForge — Roadmap & Design Spec
**Date:** 2026-03-30
**Approche retenue:** Approche 2 — Deux tracks parallèles
**Statut:** Approuvé

---

## Contexte

AgentForge est une plateforme MLOps complète pour agents IA (FastAPI + LangGraph + Next.js 15 + PostgreSQL/pgvector + Redis + Modal). Les phases 01–07 sont quasi-terminées (auth, agents, sandbox, SSE, red-team, HITL, finetune QLoRA). Le SDK Python (`/sdk`) et TypeScript (`/sdk-js`) ont des **suites de tests unitaires** (pytest / Vitest) ; les tests d’intégration Ollama sont sous `sdk/tests/integration/` (optionnels).

---

## Vue d'ensemble des tracks

### Track A — SDK Quality (indépendant)
| Phase | Contenu |
|-------|---------|
| **N1** | Ollama provider (SDK + backend) + tests unitaires SDK Python + Vitest JS |
| **N2** | Tests d'intégration `LocalAgent` × Ollama (graph, streaming, tools, conditional) |

### Track B — Nouvelles capacités (indépendant de A)
| Phase | Contenu |
|-------|---------|
| **N3** | Nœuds speech : ASR (Whisper) + TTS (OpenAI TTS / ElevenLabs) |
| **N4** | OAuth Google + Scheduling d'exécutions (cron agents) |
| **N5** | Speech training custom via Modal (Whisper finetune + TTS voice cloning) |

### Track C — Intégrations & Améliorations transverses
Validées pour implémentation après N1–N5, organisées en vagues.

---

## Phase N1 — Ollama provider + tests unitaires SDK

### Objectif
Ajouter Ollama comme premier provider LLM tiers et poser la base de test du SDK.

### Ollama provider

**Principe :** extraire la factory LLM du `if/elif` hardcodé en un module `llm_factory.py` partagé entre backend et SDK. Ollama est ajouté via `langchain_ollama.ChatOllama`.

**Backend** — nouveau fichier `app/infrastructure/orchestration/llm_factory.py` :
- `build_llm(provider, model, temperature, base_url=None, options={})` → retourne un `BaseChatModel`
- Providers supportés : `openai`, `google`/`gemini`, `ollama`
- Le `LangGraphOrchestrator` appelle `build_llm()` au lieu du bloc `if/elif` actuel

**SDK Python** — nouveau fichier `sdk/src/agentforge/llm_factory.py` (version légère, sans dépendances infra backend) :
- Même signature `build_llm()`
- `AgentModelConfig` reçoit : `base_url: Optional[str] = None`, `options: Dict[str, Any] = {}`

**API Builder :**
```python
Agent("LocalBot")
    .model("ollama", "llama3.2", base_url="http://localhost:11434")
    .llm_node("chat", system_prompt="Tu es un assistant.")
    .build()
```

### Tests unitaires SDK Python (`sdk/tests/unit/`)

| Fichier | Couverture |
|---------|-----------|
| `test_builder.py` | Fluent API : `llm_node`, `tool_node`, `subagent_node`, `edge`, `parallel_nodes`, `policy`, `build()` |
| `test_types.py` | Validation Pydantic : champs requis, limites, alias `from_`/`from` |
| `test_policy.py` | `AgentPolicy` : `max_cost`, `deny_tool`, `require_approval_for`, `build()` |
| `test_graph_validate.py` | `graph_validate.py` : graphe valide, nœud orphelin, entry point manquant |
| `test_afg_yaml.py` | Sérialisation/désérialisation AFG YAML round-trip |
| `test_llm_factory.py` | `build_llm()` retourne le bon type selon provider (mocké, pas d'appel réseau) |

Tous les tests tournent sans LLM réel (`unittest.mock.patch`).

### Tests SDK TypeScript (`sdk-js/src/__tests__/`)

Framework : **Vitest**

| Fichier | Couverture |
|---------|-----------|
| `builder.test.ts` | `AgentBuilder` : chaining, `.build()` shape correcte |
| `types.test.ts` | Validation NodeConfig, EdgeConfig, AgentDefinition |
| `client.test.ts` | `AgentForgeClient.push()` : POST mocké via `vi.mock` |

### Critères d'acceptation N1
- `cd sdk && pytest tests/unit/ -v` → 100% pass, 0 LLM calls
- `cd sdk-js && npm test` → suite Vitest verte
- Backend : `build_llm("ollama", "llama3.2")` retourne `ChatOllama` sans erreur

---

## Phase N2 — Tests d'intégration LocalAgent × Ollama

### Objectif
Valider le SDK end-to-end avec un vrai LLM local.

### Setup

`sdk/tests/conftest.py` — fixture `ollama_model` :
- Vérifie `GET http://localhost:11434/api/tags` → si KO, skip tous les tests `@pytest.mark.integration`
- Modèle par défaut : `llama3.2` (3B, léger)

`sdk/pytest.ini` :
```ini
[pytest]
markers =
    integration: requires Ollama running locally
```

### Scénarios (`sdk/tests/integration/`)

| Fichier | Scénario |
|---------|---------|
| `test_local_agent_llm.py` | Graph 1 nœud LLM Ollama → `invoke()` → dernier message est `AIMessage` |
| `test_local_agent_streaming.py` | `astream()` yield ≥1 event contenant des messages |
| `test_local_agent_tool.py` | LLM → tool (skill `instruction`) → LLM : résultat du tool injecté dans messages |
| `test_local_agent_conditional.py` | Edges conditionnelles `contains` : routing correct selon réponse LLM |
| `test_local_agent_custom_node.py` | Plugin `@node("echo")` → graph l'exécute correctement |
| `test_local_agent_policy.py` | `max_steps=1` : exécution s'arrête après 1 step |
| `test_builder_export_reload.py` | `export_json()` → `load_agent()` → `invoke()` : round-trip complet |

### Critères d'acceptation N2
- `pytest tests/integration/ -m integration -v` → tous passent avec Ollama actif
- `pytest tests/` sans Ollama → les integration tests sont SKIPPED (pas FAILED)

---

## Phase N3 — Nœuds Speech ASR + TTS

### Objectif
Agents capables de transcrire de l'audio (ASR) et de synthétiser une réponse vocale (TTS).

### State du graph
`AgentState` reçoit un champ optionnel `audio_b64: Optional[str]` pour transporter l'audio en base64 entre nœuds.

### Backend — module `app/infrastructure/speech/`

```
app/infrastructure/speech/
├── ports.py                    # ASRProvider + TTSProvider (protocoles)
├── providers/
│   ├── openai_whisper.py       # ASR via openai.audio.transcriptions.create
│   ├── openai_tts.py           # TTS via openai.audio.speech.create (tts-1, tts-1-hd)
│   └── elevenlabs_tts.py       # TTS via ElevenLabs API (voix custom, streaming)
```

**Nouveaux node types dans `LangGraphOrchestrator` :**
- `asr` : lit `audio_b64` du state → transcrit → injecte texte comme `HumanMessage`
- `tts` : lit dernier `AIMessage` → synthétise → écrit `audio_b64` dans state

**Nouvel endpoint :**
```
POST /api/v1/agents/{id}/execute/audio
Content-Type: multipart/form-data
Body: file (audio) + config (JSON)
Response: SSE avec transcription + audio final base64
```

### SDK Python

Nouvelles méthodes builder :
```python
agent = (
    Agent("VoiceAssistant")
    .model("ollama", "llama3.2")
    .asr_node("transcribe", provider="openai_whisper", language="fr")
    .llm_node("reason", system_prompt="Tu es un assistant vocal.")
    .tts_node("speak", provider="openai_tts", voice="nova")
    .edge("transcribe", "reason")
    .edge("reason", "speak")
    .build()
)
```

`NodeConfig` accepte les nouveaux types via `type: str` déjà ouvert.

### Frontend

- **Palette React Flow** : nœuds `ASR` (icône micro) et `TTS` (icône haut-parleur) avec panneaux de config (provider, voix, langue)
- **ExecutionLog** : si event SSE contient `audio_b64` → lecteur audio `<audio>` inline
- **Page agent detail** : bouton "Test vocal" → enregistreur micro → `/execute/audio` → lecture réponse

### Critères d'acceptation N3
- Graph `asr → llm → tts` s'exécute end-to-end
- Audio MP3/WAV transcrit correctement via Whisper
- Synthèse vocale retournée en base64 lisible par `<audio>`
- Nœuds visibles et configurables dans le builder React Flow

---

## Phase N4 — OAuth Google + Scheduling

### Objectif
Login social Google et planification automatique d'exécutions d'agents.

### OAuth Google

**DB — nouvelle table `social_accounts` (migration Alembic) :**
```sql
id, user_id (FK users), provider VARCHAR, provider_id VARCHAR,
email VARCHAR, access_token TEXT, refresh_token TEXT, expires_at TIMESTAMPTZ
```

**Flow backend :**
- `GET /api/v1/auth/oauth/google` → redirect Google consent screen (PKCE)
- `GET /api/v1/auth/oauth/google/callback` → échange code → crée/lie `social_account` → retourne JWT AgentForge
- Si email déjà en DB → lie le compte Google au compte existant (pas de doublon)
- Config : `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` dans `.env`

**Frontend :** bouton "Continuer avec Google" sur `/login` et `/register`. Redirect flow standard (pas de popup).

### Scheduling d'exécutions

**DB — nouvelle table `scheduled_executions` :**
```sql
id, agent_id (FK), alias VARCHAR, cron_expression VARCHAR,
input JSONB, enabled BOOLEAN, last_run_at TIMESTAMPTZ,
next_run_at TIMESTAMPTZ, created_by (FK users), created_at TIMESTAMPTZ
```

**Backend :**
- CRUD : `POST/GET/PUT/DELETE /api/v1/agents/{id}/schedules`
- Worker asyncio : toutes les 60s, lit schedules `enabled` avec `next_run_at <= now()` → dispatche via `AgentService` existant → met à jour `last_run_at` + calcule `next_run_at` (via `croniter`)
- Executions schedulées marquées `triggered_by: "schedule"` dans la table `executions`

**SDK Python :**
```python
from agentforge import AgentForgeClient
client = AgentForgeClient(api_key="...", base_url="...")
client.schedules.create(
    agent_id="uuid",
    cron="0 9 * * 1-5",
    alias="production",
    input={"messages": [{"role": "user", "content": "Rapport du jour"}]}
)
```

**Frontend :** onglet "Schedules" sur fiche agent — tableau crons actifs, toggle enable/disable, prochain run, historique.

### Critères d'acceptation N4
- Login Google → JWT valide → accès à l'app
- Schedule créé → exécution déclenchée à l'heure → apparaît dans liste executions avec flag `schedule`
- `client.schedules.create()` SDK → persiste en DB

---

## Phase N5 — Speech Training Custom via Modal

### Objectif
Fine-tuner des modèles ASR (Whisper) et TTS (voix clonée) avec le même pipeline MLOps que les LLMs.

### Data collection automatique

Nouvelle table `speech_examples` — même mécanique que `finetune_examples` :
- Quand un agent avec nœud `asr` reçoit feedback score ≥ 4 → couple `(audio_b64, transcription)` sauvegardé

Upload samples TTS :
- `POST /api/v1/speech/voice-samples` → multipart audio upload
- `GET /api/v1/speech/voice-samples` → liste des voix uploadées

### Modal functions

**`modal_functions/train_whisper.py` :**
- Base : `openai/whisper-large-v3` (HuggingFace + `transformers`)
- Fine-tune sur les speech_examples collectés
- Sauvegarde sur volume Modal `agentforge-speech-models`
- Déploie endpoint `transcribe`

**`modal_functions/train_tts.py` :**
- Base : Coqui XTTS-v2 (voice cloning open source)
- Entraîne voix personnalisée depuis samples uploadés (10–30 min audio)
- Déploie endpoint `synthesize`

### Backend

Extension `finetune_jobs.modality` : `Literal["llm", "whisper", "tts_voice"]` (champ déjà préparé dans commit récent).

Nouveaux endpoints :
```
POST /api/v1/finetune/trigger-speech
GET  /api/v1/speech/deployed
```

### Frontend

Page `/finetune` — nouvel onglet "Speech Models" :
- Upload drag-and-drop échantillons audio
- Déclenchement entraînement + progress bar (SSE polling existant)
- Liste voix custom → sélectionnable dans builder nœud `tts`

### SDK

```python
Agent("CustomVoiceBot")
    .asr_node("listen", provider="finetuned_whisper", job_id="whisper-job-uuid")
    .llm_node("think")
    .tts_node("speak", provider="finetuned_tts", voice_id="ma-voix-custom")
    .edge("listen", "think").edge("think", "speak")
    .build()
```

### Critères d'acceptation N5
- Job `whisper` lancé via UI → modèle déployé sur Modal → utilisable comme provider `asr`
- Job `tts_voice` lancé → voix custom déployée → utilisable dans nœud `tts`

---

## Track C — Intégrations & Améliorations transverses

### C1 — Nouveaux providers & modèles

| Feature | Détail technique |
|---------|-----------------|
| **Vision / multimodal** | Node type `vision` : `image_b64 + text → AIMessage`. Providers : `gpt-4o` (OpenAI) et `llava` (Ollama). Champ `image_b64` dans `AgentState`. Builder : `.vision_node("analyze", provider="ollama", model="llava")` |
| **Anthropic Claude** | Provider `anthropic` dans `llm_factory` via `langchain_anthropic.ChatAnthropic`. Modèles : `claude-opus-4-6`, `claude-sonnet-4-6` |
| **Ollama embeddings** | Provider `ollama` dans le pipeline RAG pgvector. Modèles : `nomic-embed-text`, `mxbai-embed-large`. Config dans `.env` : `EMBEDDING_PROVIDER=ollama` |

### C2 — Outillage agent — Skills & Tools natifs

**Skills built-in (sans code à écrire) :**

| Skill | Implémentation |
|-------|---------------|
| `web_search` | Tavily API ou Brave Search API |
| `code_exec` | Subprocess sandbox existant (réutilise `SubprocessSandboxRuntime`) |
| `http_fetch` | `httpx.AsyncClient` avec allowlist URL depuis `execution_policy` |
| `sql_query` | Connexion DB configurée par l'utilisateur (credentials chiffrés via `secrets_service`) |
| `send_email` | SMTP / Resend API |
| `read_file` / `write_file` | Dans sandbox isolé, répertoire monté |

Ces skills sont pré-installées dans le marketplace (via `GET /api/v1/skills/registry`) et attachables en 1 clic depuis la fiche agent.

**MCP server (complétion du commit récent) :**
- AgentForge expose ses agents comme outils MCP via `GET /api/v1/mcp/manifest`
- Compatible Claude Desktop, Cursor, tout client MCP
- Chaque agent → un outil MCP avec son schema d'input

**Long-term memory — node type `memory` :**
- Stocke/récupère des faits dans pgvector par `user_id + thread_id`
- Nouvelle table `memory_entries` (content, embedding, metadata, expires_at)
- Builder : `.memory_node("recall", top_k=5)` — injecte les faits pertinents avant le nœud LLM
- La policy `max_message_history` existante se connecte à ce mécanisme

**Templates gallery (inspiré de agency-agents) :**
- Galerie d'agents pré-configurés par catégorie : Engineering, Design, Sales, Support, Testing, Academic, Specialized
- Chaque template = agent JSON exporté (graph_definition + model_config + system_prompt + skills recommandées)
- Import en 1 clic → crée un agent dans l'espace de l'utilisateur
- Endpoint : `GET /api/v1/templates` + `POST /api/v1/agents/import/template/{slug}`

### C3 — Observabilité & Qualité

**Langfuse complet :**
- Traces LLM complètes (input/output/cost/latency par nœud) via `langfuse_span_emitter.py` existant
- Nouveau dashboard `/observability` dans l'UI : timeline executions, coût par agent, taux d'erreur
- Config : `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` dans `.env`

**Evaluation framework :**
- Scorers automatiques sur les sorties agent : RAGAS pour RAG (faithfulness, relevancy, context_recall)
- Custom scorers configurables par agent (expressions Python ou regex)
- Les scores alimentent la table `executions.eval_score` → ferme la boucle Data Flywheel avec des métriques objectives

**A/B testing agents :**
- `POST /api/v1/agents/{id}/ab-test` : body `{"version_a": 1, "version_b": 2, "input": {...}, "runs": 10}`
- Lance N executions de chaque version en parallèle, compare : score moyen, coût moyen, latence
- UI : page de résultats A/B avec graphiques comparatifs → bouton "Promouvoir B en production"

**Agent version diff :**
- `GET /api/v1/agents/{id}/versions/{v1}/diff/{v2}` → JSON diff de `graph_definition` + `model_config` + `execution_policy`
- UI : vue côte-à-côte avec highlight des nœuds ajoutés (vert) / modifiés (orange) / supprimés (rouge) dans React Flow

**Sentry opt-in :**
- `SENTRY_DSN` dans `.env` → tracking erreurs en production
- Release tracking sur deploy (tag git)

### C4 — UX / Collaboration

**Notifications :**
- Table `notification_configs` : `(user_id, event_type, channel, config)`
- Events : `execution_failed`, `schedule_triggered`, `finetune_completed`, `budget_exceeded`
- Channels : Slack webhook, email (SMTP/Resend), webhook custom
- UI : page `/settings/notifications` pour configurer

**Multi-tenant / Organisations :**
- Tables : `organizations`, `org_members` (role: owner/editor/viewer)
- Agents, skills, schedules scoped par `org_id`
- RBAC : owner peut tout, editor peut créer/modifier, viewer lecture seule
- Invitation par email → OAuth ou email/password

### C5 — Infrastructure & Dev

**Postgres HITL checkpointer :**
- Remplacer `InMemorySaver` par `langgraph-checkpoint-postgres` (package déjà cité dans STATE.md)
- HITL qui survit aux redémarrages et fonctionne en multi-workers
- Config automatique via `DATABASE_URL` existant

**CLI `watch` mode :**
- `agentforge watch agent.py` → `watchfiles` observe le fichier → rebuild + push automatique à chaque save
- Output terminal : diff des nœuds modifiés + lien vers l'agent dans l'UI

**Token streaming fin :**
- `astream_events` LangGraph (v2) au lieu d'événements par nœud
- SSE type `token` avec contenu partiel → affichage progressif dans le `ChatUI` existant
- Rétrocompatible : les clients qui n'écoutent que `node_complete` ne cassent pas

**Budget & quotas :**
- Table `budget_configs` : `(user_id, org_id, period, max_usd, alert_threshold)`
- Le `ExecutionCostMeter` existant vérifie vs budget → alerte Redis publiée → notification envoyée
- Hard stop si `max_cost_usd` dépassé (via `PolicyConfig.max_cost_usd` déjà implémenté)
- UI : widget coût sur le dashboard

---

## Mapping priorités

| Priorité | Phases | Dépendances |
|----------|--------|-------------|
| **P0** | N1, N2 (Track A) | Aucune |
| **P1** | N3 (speech providers) | N1 |
| **P1** | N4 (OAuth + scheduling) | N1 |
| **P2** | N5 (speech training) | N3 |
| **P2** | C1 (nouveaux providers) | N1 |
| **P2** | C2 (skills, MCP, memory, templates) | N2 |
| **P3** | C3 (Langfuse, eval, A/B, diff, Sentry) | N2, N3 |
| **P3** | C4 (notifs, orgs) | N4 |
| **P3** | C5 (PG checkpointer, CLI watch, streaming, budgets) | N1, N2 |

---

## État d'implémentation (suivi)

| Élément | Statut | Notes |
|---------|--------|--------|
| **N1** Ollama + tests unitaires SDK Py/JS | **Fait** | `llm_invoke` supporte `ollama` ; suites `sdk/tests/unit/` et `sdk-js` Vitest en place |
| **N2** Intégration LocalAgent × Ollama | **Fait** | `sdk/tests/integration/` + `pytest -m integration` ; skip si Ollama absent |
| **N3** ASR / TTS | **Fait** | Nœuds `asr`/`tts`, Whisper + OpenAI TTS + ElevenLabs, `POST …/execute/audio`, builder + `ExecutionLog` audio |
| **N4** OAuth Google + cron agents | **Fait** | `social_accounts` + routes OAuth ; `agent_schedules` + worker tick ; `agentforge-client.schedules` ; UI schedules sur fiche agent |
| **N5** Speech training Modal | **Partiel** | Providers HTTP `finetuned_whisper` / `finetuned_tts`, SDK + builder, `GET /api/v1/speech/deployed` ; manquent datasets `speech_examples`, scripts Modal, `POST /finetune` speech, résolution auto `job_id` → URL |
| **Track C** vagues C1–C5 | **Backlog** | Plan index : `docs/superpowers/plans/2026-03-30-track-C-backlog.md` |
| **Templates / skills catalogue** | **Partiel** | `GET /api/v1/templates` et skill templates enrichis (agents + skills installables) — la « galerie » Track C2 reste à étendre (catégories, import) |

*Correction doc vs code (N3)* : l’endpoint audio est **multipart / JSON** côté API actuelle, pas du SSE token stream pour la synthèse.

---

## Principes transverses

1. **Provider abstraction** : `llm_factory.py` partagé SDK + backend — ajouter un provider = 1 classe adapter
2. **Node extensibility** : les node types `asr`, `tts`, `vision`, `memory` suivent le même pattern plugin que `@node()` du SDK
3. **Data Flywheel** : chaque nouvelle modalité (speech, vision) alimente ses propres `*_examples` → fine-tune possible
4. **Tests first** : toute nouvelle feature de SDK inclut ses tests unitaires dans la même PR
5. **Zero breaking change SDK** : `AgentModelConfig`, `NodeConfig`, `PolicyConfig` s'étendent uniquement par champs optionnels
