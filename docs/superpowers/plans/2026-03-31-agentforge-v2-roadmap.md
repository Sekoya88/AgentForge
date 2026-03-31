# AgentForge V2 — Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformer AgentForge en une plateforme de chat conversationnelle complète où l'on peut discuter avec ses agents IA, les connecter entre eux, accéder à ses données Google, gérer son contexte utilisateur, et exporter ses agents via SDK pour d'autres projets.

**Architecture:** Le pivot central est un **Chat UI dynamique** qui remplace la page "Sandbox" confuse. Les agents deviennent des "cerveaux" LLM réutilisables avec accès aux intégrations Google. Une couche SDK permettra d'embarquer ces agents dans n'importe quel projet externe.

**Tech Stack:** FastAPI + LangGraph (backend), Next.js 14 App Router + ReactFlow (frontend), PostgreSQL + Redis, Google APIs (Gmail/Calendar), Modal (fine-tuning)

---

## Vue d'ensemble des phases

| Phase | Titre | Priorité | Complexité |
|-------|-------|----------|------------|
| 1 | Corrections rapides : modèles + skills orphelins | P0 | Faible |
| 2 | Chat UI dynamique | P0 | Haute |
| 3 | Bibliothèque de skills enrichie + agents par défaut | P1 | Moyenne |
| 4 | Contexte utilisateur en DB | P1 | Moyenne |
| 5 | Intégrations Google (Gmail + Calendar) | P1 | Haute |
| 6 | Sandbox repensée → Skill Playground | P2 | Moyenne |
| 7 | Builder UX amélioré + Cron expliqué | P2 | Moyenne |
| 8 | Import / Export + SDK | P2 | Haute |

---

## Phase 1 — Corrections rapides

### Tâche 1.1 — Mettre à jour les modèles par défaut

**Fichiers :**
- Modifier : `backend/app/domain/value_objects.py:39-44`

**Contexte :** Le validateur `default_model_for_api_providers` fixe les modèles par défaut quand `model` est `None`. Il faut passer `gemini-2.5-flash` → `gemini-3-flash` et `gpt-4o-mini` → `gpt-5.4-mini`.

- [ ] **Step 1.1.1 — Écrire le test qui vérifie les nouveaux modèles par défaut**

```python
# backend/tests/test_value_objects.py  (nouveau fichier ou ajouter à existant)
from app.domain.value_objects import AgentModelConfig

def test_default_google_model_is_gemini3():
    cfg = AgentModelConfig(provider="google")
    assert cfg.model == "gemini-3-flash"

def test_default_gemini_model_is_gemini3():
    cfg = AgentModelConfig(provider="gemini")
    assert cfg.model == "gemini-3-flash"

def test_default_openai_model_is_gpt54mini():
    cfg = AgentModelConfig(provider="openai")
    assert cfg.model == "gpt-5.4-mini"
```

- [ ] **Step 1.1.2 — Vérifier que les tests échouent**

```bash
cd backend && uv run pytest tests/test_value_objects.py -v 2>&1 | head -30
```

- [ ] **Step 1.1.3 — Mettre à jour les modèles par défaut**

Dans `backend/app/domain/value_objects.py`, modifier le `model_validator` :

```python
@model_validator(mode="after")
def default_model_for_api_providers(self) -> "AgentModelConfig":
    if self.model is not None:
        return self
    if self.provider == "openai":
        self.model = "gpt-5.4-mini"
    elif self.provider in ("google", "gemini"):
        self.model = "gemini-3-flash"
    elif self.provider == "anthropic":
        self.model = "claude-sonnet-4-5"
    return self
```

- [ ] **Step 1.1.4 — Vérifier que les tests passent**

```bash
cd backend && uv run pytest tests/test_value_objects.py -v
```

- [ ] **Step 1.1.5 — Chercher d'autres occurrences hardcodées**

```bash
cd backend && grep -rn "gemini-2.5-flash\|gpt-4o-mini" --include="*.py" .
```

Mettre à jour chaque occurrence trouvée (seeds, fixtures, docstrings de tests).

- [ ] **Step 1.1.6 — Commit**

```bash
git add backend/app/domain/value_objects.py backend/tests/test_value_objects.py
git commit -m "feat: update default models to gemini-3-flash and gpt-5.4-mini"
```

---

### Tâche 1.2 — Supprimer les skills orphelins `public_echo_registry`

**Contexte :** Trois skills nommés `public_echo_registry` apparaissent dans le builder (nœuds Tool → registry), chacun avec un UUID différent. Ce sont des artefacts de tests (`backend/tests/test_agent_skills.py`) qui ont été créés avec `is_public=True` en base de données de dev/prod. L'interface n'expose pas de bouton "delete" pour les skills du registre public qui appartiennent à d'autres users.

**Fichiers :**
- Modifier : `backend/app/api/v1/skills.py`
- Créer : `backend/alembic/versions/xxxx_cleanup_echo_registry_skills.py`

- [ ] **Step 1.2.1 — Créer une migration Alembic pour nettoyer les skills de test**

```bash
cd backend && uv run alembic revision --autogenerate -m "cleanup_echo_registry_test_skills"
```

Éditer la migration générée :

```python
def upgrade() -> None:
    # Supprime tous les skills nommés 'public_echo_registry' (artefacts de tests)
    op.execute(
        "DELETE FROM skills WHERE name = 'public_echo_registry'"
    )

def downgrade() -> None:
    pass  # Non réversible — données de test uniquement
```

- [ ] **Step 1.2.2 — Appliquer la migration**

```bash
cd backend && uv run alembic upgrade head
```

- [ ] **Step 1.2.3 — S'assurer que les tests ne recréent plus des skills publics en prod**

Dans `backend/tests/test_agent_skills.py`, vérifier que les skills créés dans les tests ont `is_public=False` ou qu'ils sont supprimés dans un `teardown` / `yield` fixture.

- [ ] **Step 1.2.4 — Commit**

```bash
git add backend/alembic/versions/ backend/tests/test_agent_skills.py
git commit -m "fix: remove orphan public_echo_registry test skills from registry"
```

---

## Phase 2 — Chat UI dynamique

**Vision :** Remplacer la page Sandbox confuse par une interface de chat centrale. Sur la page `/agents`, chaque agent a un bouton "Chat". Un panneau latéral (ou page dédiée) s'ouvre avec un chat en temps réel streamé via SSE. L'utilisateur peut charger n'importe quel agent dans le chat, voir l'historique des messages, et reprendre des conversations.

### Tâche 2.1 — Backend : endpoint de conversation persistante

**Fichiers :**
- Créer : `backend/app/domain/entities/conversation.py`
- Créer : `backend/app/infrastructure/persistence/postgres/conversation_repo.py`
- Modifier : `backend/app/infrastructure/persistence/postgres/models.py`
- Modifier : `backend/app/api/v1/agents.py`
- Modifier : `backend/alembic/versions/xxxx_add_conversations.py`

**Concept :** Une `Conversation` est un `thread_id` persistant associé à `(user_id, agent_id)`. Chaque message envoyé via le chat réutilise ce `thread_id` pour que l'agent garde le contexte.

- [ ] **Step 2.1.1 — Écrire les tests**

```python
# backend/tests/test_conversations.py
async def test_create_conversation(client, auth_headers, agent_id):
    resp = await client.post(
        f"/api/v1/agents/{agent_id}/conversations",
        headers=auth_headers,
        json={"title": "Test chat"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_id"] == str(agent_id)
    assert "thread_id" in data

async def test_list_conversations(client, auth_headers, agent_id):
    resp = await client.get(
        f"/api/v1/agents/{agent_id}/conversations",
        headers=auth_headers
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2.1.2 — Vérifier que les tests échouent**

```bash
cd backend && uv run pytest tests/test_conversations.py -v 2>&1 | head -20
```

- [ ] **Step 2.1.3 — Créer l'entité Conversation**

Créer `backend/app/domain/entities/conversation.py` :

```python
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Conversation:
    id: UUID
    user_id: UUID
    agent_id: UUID
    thread_id: str           # Identifiant LangGraph pour la mémoire
    title: str | None        # Titre optionnel (auto-généré)
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    message_count: int = 0

    @staticmethod
    def create(user_id: UUID, agent_id: UUID, title: str | None = None) -> "Conversation":
        now = datetime.utcnow()
        return Conversation(
            id=uuid4(),
            user_id=user_id,
            agent_id=agent_id,
            thread_id=str(uuid4()),
            title=title,
            created_at=now,
            updated_at=now,
        )
```

- [ ] **Step 2.1.4 — Ajouter le modèle SQLAlchemy**

Dans `backend/app/infrastructure/persistence/postgres/models.py`, ajouter après les agents :

```python
class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

- [ ] **Step 2.1.5 — Créer la migration Alembic**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_conversations_table"
cd backend && uv run alembic upgrade head
```

- [ ] **Step 2.1.6 — Créer le repository**

Créer `backend/app/infrastructure/persistence/postgres/conversation_repo.py` :

```python
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.conversation import Conversation
from app.infrastructure.persistence.postgres.models import ConversationModel
from datetime import datetime


class PostgresConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, conv: Conversation) -> Conversation:
        model = ConversationModel(
            id=conv.id, user_id=conv.user_id, agent_id=conv.agent_id,
            thread_id=conv.thread_id, title=conv.title,
            created_at=conv.created_at, updated_at=conv.updated_at,
        )
        self.session.add(model)
        await self.session.flush()
        return conv

    async def list_by_agent(self, user_id: UUID, agent_id: UUID) -> list[Conversation]:
        result = await self.session.execute(
            select(ConversationModel)
            .where(ConversationModel.user_id == user_id, ConversationModel.agent_id == agent_id)
            .order_by(ConversationModel.updated_at.desc())
        )
        rows = result.scalars().all()
        return [self._to_entity(r) for r in rows]

    async def get_by_thread(self, thread_id: str, user_id: UUID) -> Conversation | None:
        result = await self.session.execute(
            select(ConversationModel)
            .where(ConversationModel.thread_id == thread_id, ConversationModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def touch(self, thread_id: str) -> None:
        await self.session.execute(
            update(ConversationModel)
            .where(ConversationModel.thread_id == thread_id)
            .values(last_message_at=datetime.utcnow(), updated_at=datetime.utcnow(),
                    message_count=ConversationModel.message_count + 1)
        )

    async def delete(self, conv_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            select(ConversationModel)
            .where(ConversationModel.id == conv_id, ConversationModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return False
        await self.session.delete(row)
        return True

    def _to_entity(self, m: ConversationModel) -> Conversation:
        return Conversation(
            id=m.id, user_id=m.user_id, agent_id=m.agent_id,
            thread_id=m.thread_id, title=m.title,
            created_at=m.created_at, updated_at=m.updated_at,
            last_message_at=m.last_message_at, message_count=m.message_count,
        )
```

- [ ] **Step 2.1.7 — Ajouter les endpoints REST**

Dans `backend/app/api/v1/agents.py`, ajouter :

```python
@router.post("/{agent_id}/conversations", status_code=201)
async def create_conversation(
    agent_id: UUID,
    body: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = PostgresConversationRepository(db)
    conv = Conversation.create(user_id=current_user.id, agent_id=agent_id, title=body.title)
    conv = await repo.create(conv)
    await db.commit()
    return ConversationResponse.from_entity(conv)

@router.get("/{agent_id}/conversations")
async def list_conversations(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = PostgresConversationRepository(db)
    convs = await repo.list_by_agent(user_id=current_user.id, agent_id=agent_id)
    return [ConversationResponse.from_entity(c) for c in convs]

@router.delete("/{agent_id}/conversations/{conv_id}", status_code=204)
async def delete_conversation(
    agent_id: UUID,
    conv_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = PostgresConversationRepository(db)
    deleted = await repo.delete(conv_id, current_user.id)
    if not deleted:
        raise HTTPException(404, "Conversation not found")
    await db.commit()
```

Ajouter les schémas dans `backend/app/api/schemas/agent_schemas.py` :

```python
class ConversationCreateRequest(BaseModel):
    title: str | None = None

class ConversationResponse(BaseModel):
    id: UUID
    agent_id: UUID
    thread_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None
    message_count: int

    @classmethod
    def from_entity(cls, c: Conversation) -> "ConversationResponse":
        return cls(**c.__dict__)
```

- [ ] **Step 2.1.8 — Modifier l'endpoint execute pour accepter un thread_id**

Dans `AgentService.execute()`, accepter un paramètre optionnel `thread_id: str | None`. Si fourni, passer ce `thread_id` au LangGraph orchestrateur pour reprendre la mémoire de la conversation. Après exécution, appeler `repo.touch(thread_id)`.

- [ ] **Step 2.1.9 — Passer les tests**

```bash
cd backend && uv run pytest tests/test_conversations.py -v
```

- [ ] **Step 2.1.10 — Commit**

```bash
git add backend/app/domain/entities/conversation.py \
        backend/app/infrastructure/persistence/postgres/conversation_repo.py \
        backend/app/infrastructure/persistence/postgres/models.py \
        backend/app/api/v1/agents.py \
        backend/app/api/schemas/agent_schemas.py \
        backend/alembic/versions/
git commit -m "feat: add persistent conversations with thread_id for stateful chat"
```

---

### Tâche 2.2 — Frontend : panneau Chat global

**Fichiers :**
- Créer : `frontend/src/components/chat/ChatPanel.tsx`
- Créer : `frontend/src/components/chat/ChatMessage.tsx`
- Créer : `frontend/src/components/chat/AgentSelector.tsx`
- Créer : `frontend/src/components/chat/ConversationList.tsx`
- Créer : `frontend/src/hooks/useChat.ts`
- Modifier : `frontend/src/app/agents/page.tsx` (ajouter bouton "Chat")
- Modifier : `frontend/src/lib/api.ts` (ajouter endpoints conversations)

**UX cible :** Un bouton "Chat →" sur chaque agent card ouvre un drawer/slide-over sur la droite. En haut : sélecteur d'agent + liste des conversations précédentes. En bas : zone de saisie. Les messages streamés via SSE s'affichent en temps réel token par token.

- [ ] **Step 2.2.1 — Ajouter les appels API dans le client**

Dans `frontend/src/lib/api.ts`, ajouter :

```typescript
// Conversations
createConversation: async (agentId: string, title?: string) =>
  post<ConversationResponse>(`/agents/${agentId}/conversations`, { title }),

listConversations: async (agentId: string) =>
  get<ConversationResponse[]>(`/agents/${agentId}/conversations`),

deleteConversation: async (agentId: string, convId: string) =>
  del(`/agents/${agentId}/conversations/${convId}`),

// Chat (utilise l'endpoint execute existant avec thread_id)
sendMessage: async (agentId: string, message: string, threadId: string) =>
  post<ExecutionResponse>(`/agents/${agentId}/execute`, {
    input_messages: [{ role: "user", content: message }],
    thread_id: threadId,
    run_async: true,
  }),
```

- [ ] **Step 2.2.2 — Créer le hook `useChat`**

Créer `frontend/src/hooks/useChat.ts` :

```typescript
import { useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  streaming?: boolean;
}

export function useChat(agentId: string, threadId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    // Append user message immediately
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setIsStreaming(true);

    // Create placeholder for assistant response
    const assistantMsgId = crypto.randomUUID();
    setMessages(prev => [...prev, {
      id: assistantMsgId, role: "assistant", content: "", timestamp: new Date(), streaming: true,
    }]);

    try {
      const execution = await api.sendMessage(agentId, content, threadId);
      // Stream via SSE
      const token = localStorage.getItem("access_token");
      const es = new EventSource(
        `/api/v1/agents/${agentId}/executions/${execution.id}/stream?token=${token}`
      );
      eventSourceRef.current = es;

      es.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "token") {
          setMessages(prev => prev.map(m =>
            m.id === assistantMsgId
              ? { ...m, content: m.content + data.content }
              : m
          ));
        } else if (data.type === "done") {
          setMessages(prev => prev.map(m =>
            m.id === assistantMsgId ? { ...m, streaming: false } : m
          ));
          setIsStreaming(false);
          es.close();
        }
      };

      es.onerror = () => {
        setIsStreaming(false);
        es.close();
      };
    } catch (err) {
      setIsStreaming(false);
    }
  }, [agentId, threadId]);

  return { messages, isStreaming, sendMessage };
}
```

- [ ] **Step 2.2.3 — Créer le composant ChatPanel**

Créer `frontend/src/components/chat/ChatPanel.tsx` (composant drawer complet avec liste de messages, input, bouton d'envoi, scroll-to-bottom automatique). Chaque message `streaming: true` affiche un curseur clignotant.

- [ ] **Step 2.2.4 — Créer le sélecteur d'agent dans le chat**

Créer `frontend/src/components/chat/AgentSelector.tsx` : un `<Select>` qui liste tous les agents. Au changement, crée ou charge une conversation existante. Permet de passer d'un agent à l'autre sans quitter le chat.

- [ ] **Step 2.2.5 — Ajouter le bouton "Chat" sur les agent cards**

Dans `frontend/src/app/agents/page.tsx`, ajouter un bouton "Chat →" sur chaque agent card. Cliquer ouvre le `ChatPanel` avec cet agent pré-sélectionné (crée une nouvelle conversation ou charge la dernière).

- [ ] **Step 2.2.6 — Ajouter une page dédiée `/chat`**

Créer `frontend/src/app/chat/page.tsx` : page plein écran avec `AgentSelector` à gauche, `ConversationList` en dessous, et `ChatPanel` à droite. Accessible via le menu de navigation. C'est la page principale de la plateforme.

- [ ] **Step 2.2.7 — Commit**

```bash
git add frontend/src/components/chat/ frontend/src/hooks/useChat.ts \
        frontend/src/app/chat/ frontend/src/lib/api.ts
git commit -m "feat: add dynamic chat UI with agent selector and SSE streaming"
```

---

## Phase 3 — Bibliothèque de skills enrichie + agents par défaut

### Tâche 3.1 — Nouveaux skill templates (catégories productivity, google, code)

**Fichiers :**
- Modifier : `backend/app/domain/skill_templates.py`

**Skills à ajouter** (15 nouveaux) :

- [ ] **Step 3.1.1 — Écrire le test de couverture des templates**

```python
# backend/tests/test_skill_templates.py
from app.domain.skill_templates import SKILL_TEMPLATES

EXPECTED_SKILLS = [
    "gmail_reader", "gmail_sender", "calendar_events", "calendar_create",
    "notion_create_page", "slack_message", "github_issue", "arxiv_search",
    "sentiment_analysis", "meeting_notes", "action_items", "pr_description",
    "regex_extractor", "markdown_formatter", "date_calculator",
]

def test_all_expected_skills_present():
    names = {t["name"] for t in SKILL_TEMPLATES}
    missing = [s for s in EXPECTED_SKILLS if s not in names]
    assert missing == [], f"Missing skill templates: {missing}"

def test_all_templates_have_required_fields():
    required = {"name", "description", "skill_type", "permissions", "is_public", "category"}
    for t in SKILL_TEMPLATES:
        missing = required - set(t.keys())
        assert not missing, f"Template '{t['name']}' missing: {missing}"
```

- [ ] **Step 3.1.2 — Vérifier que les tests échouent**

```bash
cd backend && uv run pytest tests/test_skill_templates.py -v 2>&1 | head -20
```

- [ ] **Step 3.1.3 — Ajouter les skill templates dans `skill_templates.py`**

Ajouter à la liste `SKILL_TEMPLATES` :

```python
# ── Productivity skills ──────────────────────────────────────────
{
    "name": "meeting_notes",
    "description": "Formatte des notes de réunion brutes en compte-rendu structuré",
    "skill_type": "instruction",
    "source_code": "",
    "instructions": (
        "Tu es un assistant de réunion professionnel.\n\n"
        "Étant donné des notes brutes de réunion:\n"
        "1. Extraire: Date, Participants, Ordre du jour\n"
        "2. Résumer les décisions prises (bullet points)\n"
        "3. Lister les actions avec responsable et deadline si mentionnés\n"
        "4. Format: Markdown structuré avec sections ##\n"
        "5. Garder un ton professionnel et neutre"
    ),
    "parameters_schema": {},
    "permissions": [],
    "is_public": True,
    "category": "productivity",
},
{
    "name": "action_items",
    "description": "Extrait les tâches et actions à faire depuis un texte",
    "skill_type": "instruction",
    "source_code": "",
    "instructions": (
        "Tu es un assistant d'extraction de tâches.\n\n"
        "Depuis le texte fourni:\n"
        "1. Identifie toutes les actions à faire (verbes d'action + objet)\n"
        "2. Pour chaque action, extraire: Quoi / Qui / Quand (si mentionné)\n"
        "3. Retourner en JSON: [{\"task\": str, \"owner\": str|null, \"due\": str|null}]\n"
        "4. Prioritiser: urgent > important > normal"
    ),
    "parameters_schema": {},
    "permissions": [],
    "is_public": True,
    "category": "productivity",
},
{
    "name": "pr_description",
    "description": "Génère une description de Pull Request depuis un git diff ou changelog",
    "skill_type": "instruction",
    "source_code": "",
    "instructions": (
        "Tu es un développeur senior qui rédige des descriptions de PR.\n\n"
        "Depuis le diff ou les commits fournis:\n"
        "1. Rédiger un titre clair (< 72 caractères)\n"
        "2. Section ## Summary: 2-3 bullet points du changement principal\n"
        "3. Section ## Changes: liste technique détaillée\n"
        "4. Section ## Testing: comment tester ces changements\n"
        "5. Mentionner les breaking changes si présents"
    ),
    "parameters_schema": {},
    "permissions": [],
    "is_public": True,
    "category": "development",
},
{
    "name": "sentiment_analysis",
    "description": "Analyse le sentiment d'un texte (positif/négatif/neutre + score)",
    "skill_type": "instruction",
    "source_code": "",
    "instructions": (
        "Tu es un expert en analyse de sentiment.\n\n"
        "Depuis le texte fourni:\n"
        "1. Déterminer le sentiment global: positif / négatif / neutre / mixte\n"
        "2. Score de 0 à 1 (0 = très négatif, 0.5 = neutre, 1 = très positif)\n"
        "3. Identifier les phrases clés qui justifient ce sentiment\n"
        "4. Retourner JSON: {\"sentiment\": str, \"score\": float, \"key_phrases\": [str]}\n"
        "5. Si le texte est dans une autre langue, analyser quand même et noter la langue"
    ),
    "parameters_schema": {},
    "permissions": [],
    "is_public": True,
    "category": "data",
},
{
    "name": "markdown_formatter",
    "description": "Convertit du texte brut ou HTML en Markdown propre",
    "skill_type": "code",
    "source_code": (
        "import re\n\n\n"
        "def run(text: str) -> str:\n"
        "    # Normalize line endings\n"
        "    text = text.replace('\\r\\n', '\\n').replace('\\r', '\\n')\n"
        "    # Convert basic HTML tags\n"
        "    text = re.sub(r'<br\\s*/?>', '\\n', text, flags=re.IGNORECASE)\n"
        "    text = re.sub(r'<p>(.*?)</p>', r'\\1\\n\\n', text, flags=re.DOTALL | re.IGNORECASE)\n"
        "    text = re.sub(r'<h([1-6])>(.*?)</h\\1>', lambda m: '#' * int(m.group(1)) + ' ' + m.group(2) + '\\n', text, flags=re.DOTALL | re.IGNORECASE)\n"
        "    text = re.sub(r'<strong>(.*?)</strong>', r'**\\1**', text, flags=re.DOTALL | re.IGNORECASE)\n"
        "    text = re.sub(r'<em>(.*?)</em>', r'*\\1*', text, flags=re.DOTALL | re.IGNORECASE)\n"
        "    text = re.sub(r'<[^>]+>', '', text)  # Strip remaining HTML\n"
        "    # Normalize multiple blank lines\n"
        "    text = re.sub(r'\\n{3,}', '\\n\\n', text)\n"
        "    return text.strip()\n"
    ),
    "instructions": None,
    "parameters_schema": {},
    "permissions": [],
    "is_public": True,
    "category": "text",
},
{
    "name": "date_calculator",
    "description": "Calcule des dates relatives (dans X jours, dernier lundi, etc.)",
    "skill_type": "code",
    "source_code": (
        "from datetime import datetime, timedelta\n"
        "import re\n"
        "import json\n\n\n"
        "def run(query: str) -> str:\n"
        "    now = datetime.utcnow()\n"
        "    q = query.lower().strip()\n"
        "    result = {}\n"
        "    if m := re.search(r'in (\\d+) days?', q):\n"
        "        d = now + timedelta(days=int(m.group(1)))\n"
        "        result['date'] = d.strftime('%Y-%m-%d')\n"
        "        result['weekday'] = d.strftime('%A')\n"
        "    elif m := re.search(r'(\\d+) days? ago', q):\n"
        "        d = now - timedelta(days=int(m.group(1)))\n"
        "        result['date'] = d.strftime('%Y-%m-%d')\n"
        "        result['weekday'] = d.strftime('%A')\n"
        "    elif 'today' in q:\n"
        "        result['date'] = now.strftime('%Y-%m-%d')\n"
        "        result['weekday'] = now.strftime('%A')\n"
        "    elif 'tomorrow' in q:\n"
        "        d = now + timedelta(days=1)\n"
        "        result['date'] = d.strftime('%Y-%m-%d')\n"
        "        result['weekday'] = d.strftime('%A')\n"
        "    else:\n"
        "        result['date'] = now.strftime('%Y-%m-%d')\n"
        "        result['note'] = f'Could not parse: {query}'\n"
        "    result['now_utc'] = now.strftime('%Y-%m-%d %H:%M UTC')\n"
        "    return json.dumps(result, indent=2)\n"
    ),
    "instructions": None,
    "parameters_schema": {},
    "permissions": [],
    "is_public": True,
    "category": "productivity",
},
{
    "name": "regex_extractor",
    "description": "Applique une regex sur un texte et retourne les groupes capturés",
    "skill_type": "code",
    "source_code": (
        "import re\n"
        "import json\n\n\n"
        "def run(input_text: str) -> str:\n"
        "    lines = input_text.strip().split('\\n', 1)\n"
        "    if len(lines) < 2:\n"
        "        return json.dumps({'error': 'Format: première ligne = regex, reste = texte'})\n"
        "    pattern, text = lines[0].strip(), lines[1]\n"
        "    try:\n"
        "        matches = re.findall(pattern, text)\n"
        "        return json.dumps({'pattern': pattern, 'matches': matches, 'count': len(matches)}, indent=2)\n"
        "    except re.error as e:\n"
        "        return json.dumps({'error': f'Invalid regex: {e}'})\n"
    ),
    "instructions": None,
    "parameters_schema": {},
    "permissions": [],
    "is_public": True,
    "category": "data",
},
# ── Google integration skills (nécessitent le token OAuth Google) ──
{
    "name": "gmail_reader",
    "description": "Lit les N derniers emails Gmail de l'utilisateur",
    "skill_type": "instruction",
    "source_code": "",
    "instructions": (
        "Tu as accès aux emails Gmail de l'utilisateur via l'outil `read_gmail`.\n\n"
        "Quand l'utilisateur demande ses emails:\n"
        "1. Appeler read_gmail avec le nombre d'emails souhaités (défaut: 10)\n"
        "2. Présenter chaque email: De / Date / Sujet / Résumé (2 lignes max)\n"
        "3. Si l'utilisateur veut lire un email spécifique, montrer le corps complet\n"
        "4. Proposer des actions: répondre, archiver, transférer"
    ),
    "parameters_schema": {},
    "permissions": ["google_gmail"],
    "is_public": False,
    "category": "google",
},
{
    "name": "gmail_sender",
    "description": "Compose et envoie des emails via Gmail",
    "skill_type": "instruction",
    "source_code": "",
    "instructions": (
        "Tu peux envoyer des emails via Gmail avec l'outil `send_gmail`.\n\n"
        "Processus:\n"
        "1. Demander: destinataire(s), sujet, corps du message\n"
        "2. Rédiger un email professionnel et clair\n"
        "3. Montrer un aperçu à l'utilisateur avant envoi\n"
        "4. Demander confirmation ('Voulez-vous envoyer cet email?')\n"
        "5. Envoyer seulement après confirmation explicite\n"
        "6. Confirmer l'envoi avec l'ID du message"
    ),
    "parameters_schema": {},
    "permissions": ["google_gmail_send"],
    "is_public": False,
    "category": "google",
},
{
    "name": "calendar_events",
    "description": "Consulte les événements du calendrier Google de l'utilisateur",
    "skill_type": "instruction",
    "source_code": "",
    "instructions": (
        "Tu accèdes au Google Calendar de l'utilisateur via `read_calendar`.\n\n"
        "Quand l'utilisateur demande son agenda:\n"
        "1. Appeler read_calendar avec la plage de dates (défaut: cette semaine)\n"
        "2. Lister les événements: Heure / Titre / Lieu / Participants\n"
        "3. Signaler les conflits si présents\n"
        "4. Suggérer des créneaux libres si demandé"
    ),
    "parameters_schema": {},
    "permissions": ["google_calendar"],
    "is_public": False,
    "category": "google",
},
{
    "name": "calendar_create",
    "description": "Crée des événements dans le calendrier Google",
    "skill_type": "instruction",
    "source_code": "",
    "instructions": (
        "Tu peux créer des événements dans Google Calendar via `create_calendar_event`.\n\n"
        "Processus:\n"
        "1. Collecter: titre, date+heure début, date+heure fin, participants (optionnel), lieu (optionnel)\n"
        "2. Vérifier la disponibilité sur le créneau demandé\n"
        "3. Montrer un récapitulatif avant création\n"
        "4. Créer l'événement après confirmation\n"
        "5. Retourner le lien Google Calendar de l'événement créé"
    ),
    "parameters_schema": {},
    "permissions": ["google_calendar_write"],
    "is_public": False,
    "category": "google",
},
{
    "name": "arxiv_search",
    "description": "Recherche des articles scientifiques sur ArXiv",
    "skill_type": "code",
    "source_code": (
        "import httpx\n"
        "import xml.etree.ElementTree as ET\n"
        "import json\n\n\n"
        "def run(query: str) -> str:\n"
        "    url = 'http://export.arxiv.org/api/query'\n"
        "    params = {'search_query': f'all:{query}', 'max_results': 5, 'sortBy': 'relevance'}\n"
        "    resp = httpx.get(url, params=params, timeout=15)\n"
        "    resp.raise_for_status()\n"
        "    ns = {'atom': 'http://www.w3.org/2005/Atom'}\n"
        "    root = ET.fromstring(resp.text)\n"
        "    results = []\n"
        "    for entry in root.findall('atom:entry', ns):\n"
        "        results.append({\n"
        "            'title': entry.findtext('atom:title', namespaces=ns, default='').strip(),\n"
        "            'summary': (entry.findtext('atom:summary', namespaces=ns, default='').strip())[:300],\n"
        "            'url': entry.findtext('atom:id', namespaces=ns, default='').strip(),\n"
        "            'published': entry.findtext('atom:published', namespaces=ns, default=''),\n"
        "        })\n"
        "    return json.dumps(results, indent=2)\n"
    ),
    "instructions": None,
    "parameters_schema": {},
    "permissions": ["network"],
    "is_public": True,
    "category": "research",
},
```

- [ ] **Step 3.1.4 — Vérifier que les tests passent**

```bash
cd backend && uv run pytest tests/test_skill_templates.py -v
```

- [ ] **Step 3.1.5 — Commit**

```bash
git add backend/app/domain/skill_templates.py backend/tests/test_skill_templates.py
git commit -m "feat: add 13 new skill templates (productivity, google, research, data)"
```

---

### Tâche 3.2 — Agents par défaut (seed data amélioré)

**Fichiers :**
- Modifier : `backend/app/infrastructure/persistence/postgres/seed.py` (ou fichier d'init existant)

**Vision :** Quand un nouveau user s'inscrit, créer 5 agents pré-configurés et fonctionnels immédiatement.

- [ ] **Step 3.2.1 — Identifier le fichier de seed**

```bash
grep -rn "seed\|default_agent\|create.*agent" backend/app --include="*.py" -l
```

- [ ] **Step 3.2.2 — Créer les agents par défaut**

Dans le fichier de seed, définir ces 5 agents :

**Agent 1 — Assistant personnel** (provider: google, modèle: gemini-3-flash)
- System prompt: "Tu es un assistant personnel intelligent. Tu peux aider avec l'organisation, la rédaction d'emails, la consultation du calendrier et répondre à toutes les questions. Réponds toujours en français sauf si l'utilisateur parle une autre langue."
- Nœuds: 1 nœud LLM avec le system prompt ci-dessus
- Skills attachés: `summarize`, `email_drafter`, `meeting_notes`

**Agent 2 — Coach Code** (provider: anthropic, modèle: claude-sonnet-4-5)
- System prompt: "Tu es un senior software engineer qui revoit et améliore du code. Tu expliques toujours le pourquoi de tes suggestions. Tu es direct et concis."
- Nœuds: 1 nœud LLM
- Skills attachés: `code_review`, `pr_description`, `web_search`

**Agent 3 — Analyste de données** (provider: openai, modèle: gpt-5.4-mini)
- System prompt: "Tu es un analyste de données. Tu extrais des insights depuis des textes, CSV, et JSON. Tu présentes toujours tes résultats de façon structurée avec des métriques clés."
- Nœuds: 1 nœud LLM
- Skills attachés: `data_extract`, `sentiment_analysis`, `json_transform`, `text_stats`

**Agent 4 — Secrétaire calendrier** (provider: google, modèle: gemini-3-flash)
- System prompt: "Tu gères l'agenda et les emails de l'utilisateur. Tu consultes son calendrier, crées des événements, et gères ses emails. Tu demandes toujours confirmation avant d'envoyer ou créer quelque chose."
- Nœuds: 1 nœud LLM
- Skills attachés: `calendar_events`, `calendar_create`, `gmail_reader`, `gmail_sender`

**Agent 5 — Chercheur** (provider: google, modèle: gemini-3-flash)
- System prompt: "Tu es un chercheur qui explore et synthétise des informations depuis le web et la littérature scientifique. Tu cites toujours tes sources et distingues les faits des opinions."
- Nœuds: 1 nœud LLM
- Skills attachés: `web_search`, `arxiv_search`, `summarize`

- [ ] **Step 3.2.3 — Vérifier en local que les agents par défaut se créent**

```bash
cd backend && uv run python -m app.infrastructure.persistence.postgres.seed --user-email test@test.com
```

- [ ] **Step 3.2.4 — Commit**

```bash
git commit -m "feat: add 5 functional default agents for new users"
```

---

## Phase 4 — Contexte utilisateur en DB

**Vision :** Chaque utilisateur peut définir un "contexte" (biographie, préférences, style de communication, informations récurrentes). Ce contexte est injecté automatiquement dans le system prompt de chaque agent qui le souhaite.

### Tâche 4.1 — Table user_context

**Fichiers :**
- Créer : `backend/app/domain/entities/user_context.py`
- Modifier : `backend/app/infrastructure/persistence/postgres/models.py`
- Créer : `backend/alembic/versions/xxxx_add_user_context.py`
- Modifier : `backend/app/api/v1/settings.py` (ou créer `user_context.py`)
- Modifier : `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`

- [ ] **Step 4.1.1 — Écrire le test**

```python
# backend/tests/test_user_context.py
async def test_upsert_user_context(client, auth_headers):
    resp = await client.put(
        "/api/v1/me/context",
        headers=auth_headers,
        json={"bio": "Je suis développeur fullstack.", "preferences": {"language": "fr", "tone": "casual"}}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bio"] == "Je suis développeur fullstack."

async def test_get_user_context(client, auth_headers):
    resp = await client.get("/api/v1/me/context", headers=auth_headers)
    assert resp.status_code == 200
```

- [ ] **Step 4.1.2 — Ajouter le modèle SQLAlchemy**

```python
class UserContextModel(Base):
    __tablename__ = "user_contexts"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)           # "Je m'appelle Nicolas, développeur..."
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # {"language": "fr", "tone": "casual"}
    custom_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # Données libres
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 4.1.3 — Ajouter les endpoints `GET/PUT /api/v1/me/context`**

L'endpoint PUT fait un upsert (insert si absent, update si présent).

- [ ] **Step 4.1.4 — Injecter le contexte dans les executions**

Dans `AgentService.execute()`, avant d'appeler l'orchestrateur, charger le `UserContextModel` de l'utilisateur. Si présent et si l'agent a `use_user_context: true` dans sa config, prepend le contexte au system prompt du premier nœud LLM :

```
[User context]
{bio}
Preferences: {preferences}
---
{original system prompt}
```

- [ ] **Step 4.1.5 — Frontend : section "Mon contexte" dans Profile**

Dans `frontend/src/app/profile/page.tsx`, ajouter une section "Mon contexte" avec :
- Un textarea pour la biographie
- Des champs pour les préférences (langue, ton)
- Un champ JSON libre pour les données custom (ex: "mon entreprise est X")

- [ ] **Step 4.1.6 — Commit**

```bash
git commit -m "feat: add user context storage with automatic injection in agent executions"
```

---

## Phase 5 — Intégrations Google (Gmail + Calendar)

**Contexte :** L'infrastructure OAuth Google existe déjà (`SocialAccountModel` stocke les tokens chiffrés, `GoogleOAuthService` gère le flow). Il faut ajouter les scopes Gmail + Calendar à l'OAuth, puis créer des "built-in tools" que le LangGraph orchestrateur peut appeler.

### Tâche 5.1 — Étendre les scopes OAuth Google

**Fichiers :**
- Modifier : `backend/app/infrastructure/auth/google_oauth_flow.py`
- Modifier : `backend/app/config.py`

- [ ] **Step 5.1.1 — Ajouter les scopes Gmail et Calendar**

Dans `google_oauth_flow.py`, modifier la liste des scopes :

```python
GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
```

- [ ] **Step 5.1.2 — Stocker les scopes accordés**

Dans `SocialAccountModel`, ajouter une colonne `scopes: list[str]` (ARRAY) pour savoir quels scopes ont été accordés.

- [ ] **Step 5.1.3 — UI de reconnexion**

Dans `frontend/src/app/settings/page.tsx`, si l'user est connecté Google mais n'a pas les scopes Gmail/Calendar, afficher un bouton "Autoriser Gmail + Agenda" qui relance le flow OAuth avec les nouveaux scopes.

### Tâche 5.2 — Service Google API

**Fichiers :**
- Créer : `backend/app/infrastructure/integrations/google_api_service.py`

- [ ] **Step 5.2.1 — Écrire les tests (mocked)**

```python
# backend/tests/test_google_api_service.py
from unittest.mock import AsyncMock, patch
from app.infrastructure.integrations.google_api_service import GoogleApiService

async def test_list_emails_returns_list(mock_google_service):
    emails = await mock_google_service.list_emails(max_results=5)
    assert isinstance(emails, list)
    assert len(emails) <= 5

async def test_create_event_returns_event_id(mock_google_service):
    event_id = await mock_google_service.create_event(
        title="Réunion", start="2026-04-01T10:00:00", end="2026-04-01T11:00:00"
    )
    assert event_id is not None
```

- [ ] **Step 5.2.2 — Créer le service**

Créer `backend/app/infrastructure/integrations/google_api_service.py` :

```python
import httpx
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EmailSummary:
    id: str
    from_: str
    subject: str
    date: str
    snippet: str


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: str
    end: str
    location: str | None
    attendees: list[str]


class GoogleApiService:
    GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"
    CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"

    def __init__(self, access_token: str):
        self.headers = {"Authorization": f"Bearer {access_token}"}

    async def list_emails(self, max_results: int = 10, query: str = "") -> list[EmailSummary]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.GMAIL_BASE}/users/me/messages",
                headers=self.headers,
                params={"maxResults": max_results, "q": query or "in:inbox"},
            )
            resp.raise_for_status()
            messages = resp.json().get("messages", [])
            results = []
            for msg in messages[:max_results]:
                detail = await client.get(
                    f"{self.GMAIL_BASE}/users/me/messages/{msg['id']}",
                    headers=self.headers,
                    params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                )
                detail.raise_for_status()
                d = detail.json()
                headers_map = {h["name"]: h["value"] for h in d.get("payload", {}).get("headers", [])}
                results.append(EmailSummary(
                    id=msg["id"],
                    from_=headers_map.get("From", ""),
                    subject=headers_map.get("Subject", ""),
                    date=headers_map.get("Date", ""),
                    snippet=d.get("snippet", ""),
                ))
            return results

    async def send_email(self, to: str, subject: str, body: str) -> str:
        """Encode and send an email. Returns message ID."""
        import base64
        from email.mime.text import MIMEText
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GMAIL_BASE}/users/me/messages/send",
                headers=self.headers,
                json={"raw": raw},
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def list_events(self, days_ahead: int = 7) -> list[CalendarEvent]:
        time_min = datetime.utcnow().isoformat() + "Z"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.CALENDAR_BASE}/calendars/primary/events",
                headers=self.headers,
                params={
                    "timeMin": time_min,
                    "maxResults": 20,
                    "singleEvents": True,
                    "orderBy": "startTime",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return [
                CalendarEvent(
                    id=e["id"],
                    title=e.get("summary", "Sans titre"),
                    start=e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                    end=e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
                    location=e.get("location"),
                    attendees=[a["email"] for a in e.get("attendees", [])],
                )
                for e in items
            ]

    async def create_event(
        self, title: str, start: str, end: str,
        location: str | None = None, attendees: list[str] | None = None,
    ) -> str:
        body = {
            "summary": title,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.CALENDAR_BASE}/calendars/primary/events",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()["id"]
```

### Tâche 5.3 — Intégrer Google API dans l'orchestrateur

**Fichiers :**
- Modifier : `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`
- Modifier : `backend/app/application/services/agent_service.py`

- [ ] **Step 5.3.1 — Créer les built-in tools Google**

Dans l'orchestrateur, ajouter une fonction `build_google_tools(google_service: GoogleApiService)` qui retourne une liste de tools LangChain :

```python
from langchain_core.tools import tool

def build_google_tools(svc: GoogleApiService) -> list:
    @tool
    async def read_gmail(max_results: int = 10) -> str:
        """List recent emails from Gmail inbox."""
        emails = await svc.list_emails(max_results=max_results)
        return json.dumps([e.__dict__ for e in emails], default=str, indent=2)

    @tool
    async def send_gmail(to: str, subject: str, body: str) -> str:
        """Send an email via Gmail."""
        msg_id = await svc.send_email(to=to, subject=subject, body=body)
        return f"Email sent. Message ID: {msg_id}"

    @tool
    async def read_calendar(days_ahead: int = 7) -> str:
        """List upcoming calendar events."""
        events = await svc.list_events(days_ahead=days_ahead)
        return json.dumps([e.__dict__ for e in events], default=str, indent=2)

    @tool
    async def create_calendar_event(title: str, start: str, end: str, location: str = "", attendees: str = "") -> str:
        """Create a calendar event. start/end format: 2026-04-01T10:00:00"""
        att = [a.strip() for a in attendees.split(",") if a.strip()] if attendees else []
        event_id = await svc.create_event(title=title, start=start, end=end, location=location or None, attendees=att)
        return f"Event created. ID: {event_id}"

    return [read_gmail, send_gmail, read_calendar, create_calendar_event]
```

- [ ] **Step 5.3.2 — Injecter les tools Google dans AgentService**

Dans `AgentService.execute()`, après avoir chargé les secrets, charger le token Google du user (si disponible) et créer `GoogleApiService`. Passer les tools Google à l'orchestrateur.

- [ ] **Step 5.3.3 — UI : badge "Google connecté" dans le builder**

Dans le builder, si un skill a `permission: google_gmail` ou `google_calendar`, afficher un badge "Requiert Google" et vérifier si l'user a le token Google.

- [ ] **Step 5.3.4 — Commit**

```bash
git commit -m "feat: add Gmail and Calendar built-in tools for agents via Google OAuth"
```

---

## Phase 6 — Sandbox repensée → Skill Playground

**Contexte :** La Sandbox actuelle permet d'exécuter du Python brut. Son utilité n'est pas claire pour l'utilisateur. La rendre utile en la transformant en **Skill Development Playground** : l'utilisateur écrit du code Python, le teste directement, et peut le sauvegarder comme skill.

### Tâche 6.1 — Skill Playground

**Fichiers :**
- Modifier : `frontend/src/app/sandbox/page.tsx`
- Modifier : `frontend/src/app/sandbox/` (renommer ou rediriger vers `/playground`)

- [ ] **Step 6.1.1 — Rediriger `/sandbox` vers `/playground`**

Créer `frontend/src/app/sandbox/page.tsx` avec une redirection :
```typescript
redirect('/playground');
```

- [ ] **Step 6.1.2 — Créer `/playground`**

Créer `frontend/src/app/playground/page.tsx` avec :
- **En-tête clair** : "Skill Playground — Écrivez et testez du code Python, sauvegardez comme skill"
- **Éditeur Monaco** (déjà utilisé dans le builder ?) avec coloration syntaxique Python
- **Template starter** : une fonction `def run(x: str) -> str:` pré-remplie
- **Zone d'input** : champ texte pour passer l'argument à `run()`
- **Bouton "Test"** : appelle `/api/v1/sandbox/run` et affiche le résultat
- **Bouton "Sauvegarder comme skill"** : ouvre un dialog pour nommer le skill et le créer via `POST /api/v1/skills`
- **Liste "Mes skills récents"** : lien rapide pour ouvrir les skills existants dans le playground

- [ ] **Step 6.1.3 — Mettre à jour la navigation**

Remplacer "Sandbox" par "Playground" dans le menu de navigation principal.

- [ ] **Step 6.1.4 — Commit**

```bash
git commit -m "feat: transform Sandbox into Skill Playground with save-as-skill button"
```

---

## Phase 7 — Builder UX + Cron expliqué

### Tâche 7.1 — Améliorer l'UX du builder

**Problèmes identifiés :**
- L'utilisateur ne sait pas comment configurer un nœud LLM
- Aucun template de départ (canvas vide)
- Les skills attachés ne montrent pas leur description

**Fichiers :**
- Modifier : `frontend/src/app/agents/[id]/builder/page.tsx`
- Créer : `frontend/src/components/builder/NodeTemplateModal.tsx`
- Créer : `frontend/src/components/builder/QuickStartTemplates.tsx`

- [ ] **Step 7.1.1 — Canvas vide → templates de démarrage**

Quand un agent est créé, au lieu d'un canvas vide, afficher 3 templates :
1. **Chat simple** : 1 nœud LLM avec system prompt
2. **Outil + LLM** : 1 nœud Tool → 1 nœud LLM
3. **Pipeline** : Tool → LLM → Tool

Cliquer sur un template pré-remplit le graph.

- [ ] **Step 7.1.2 — Panel de configuration des nœuds guidé**

Pour le nœud LLM, le panel de droite doit afficher :
- Champ "Rôle de l'agent" avec placeholder : "Tu es un assistant qui..."
- Sélecteur de provider/modèle avec description du modèle (speed/quality)
- Toggle "Utiliser le contexte utilisateur"
- Tooltip sur chaque option

- [ ] **Step 7.1.3 — Afficher les descriptions des skills dans le builder**

Dans le panneau "Attach skills", afficher pour chaque skill : nom, description courte, catégorie, badge si nécessite Google.

- [ ] **Step 7.1.4 — Commit**

```bash
git commit -m "feat: improve builder UX with quickstart templates and guided node config"
```

---

### Tâche 7.2 — Cron Schedules : explication et UX

**Contexte actuel :** Le cron schedule permet de lancer un agent automatiquement selon une planification (toutes les heures, tous les jours à 9h, etc.). L'utilisateur ne comprend pas à quoi ça sert.

**Fichiers :**
- Modifier : `frontend/src/app/agents/[id]/page.tsx` (section Schedules)

- [ ] **Step 7.2.1 — Ajouter une description claire des cron schedules**

Remplacer la section SCHEDULES (CRON) actuelle par :

```
⏰ Automatisation — Lancer cet agent automatiquement

Les automatisations permettent à cet agent de s'exécuter sans intervention,
par exemple pour envoyer un résumé quotidien de vos emails, vérifier votre
agenda chaque matin, ou faire un rapport hebdomadaire.

Exemples :
• "0 9 * * 1-5"  → Chaque jour ouvrable à 9h
• "0 8 * * 1"    → Chaque lundi à 8h
• "*/30 * * * *"  → Toutes les 30 minutes
```

- [ ] **Step 7.2.2 — Ajouter des presets de cron**

Au lieu d'un champ cron brut, ajouter des presets cliquables :
- "Chaque jour à 9h" → `0 9 * * *`
- "Chaque lundi matin" → `0 8 * * 1`
- "Chaque heure" → `0 * * * *`
- "Personnalisé" → affiche le champ cron brut avec un lien "Aide cron"

- [ ] **Step 7.2.3 — Commit**

```bash
git commit -m "feat: improve cron schedule UX with presets and clear explanations"
```

---

## Phase 8 — Import / Export + SDK

### Tâche 8.1 — Export / Import d'agents

**Vision :** Un agent est exportable en JSON complet (graph, config, skills inline, metadata). Ce JSON peut être importé dans n'importe quelle instance d'AgentForge.

**Fichiers :**
- Modifier : `backend/app/api/v1/agents.py`
- Modifier : `backend/app/application/services/agent_service.py`
- Modifier : `frontend/src/app/agents/page.tsx`

- [ ] **Step 8.1.1 — Endpoint d'export**

```python
@router.get("/{agent_id}/export")
async def export_agent(
    agent_id: UUID,
    include_skills: bool = True,
    current_user: User = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """Export agent as a portable JSON bundle."""
    bundle = await service.export_bundle(agent_id, current_user.id, include_skills=include_skills)
    return JSONResponse(content=bundle, headers={
        "Content-Disposition": f"attachment; filename=agent-{agent_id}.json"
    })
```

Format JSON exporté :
```json
{
  "agentforge_version": "2.0",
  "exported_at": "2026-03-31T...",
  "agent": {
    "name": "Assistant personnel",
    "description": "...",
    "graph_definition": {...},
    "model_config": {...},
    "execution_policy": {...}
  },
  "skills": [
    { "name": "summarize", "skill_type": "instruction", "instructions": "...", ... }
  ]
}
```

- [ ] **Step 8.1.2 — Endpoint d'import**

```python
@router.post("/import", status_code=201)
async def import_agent(
    bundle: AgentImportBundle,
    current_user: User = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """Import an agent from a JSON bundle."""
    agent = await service.import_bundle(bundle, current_user.id)
    return AgentResponse.from_entity(agent)
```

- [ ] **Step 8.1.3 — Frontend : bouton Export + modal Import**

Sur la page `/agents`, ajouter :
- Bouton "⬇ Export" sur chaque agent card → télécharge le JSON
- Bouton "⬆ Import JSON" en haut → ouvre un modal avec file upload ou paste JSON

- [ ] **Step 8.1.4 — Commit**

```bash
git commit -m "feat: add agent import/export as portable JSON bundles"
```

---

### Tâche 8.2 — SDK Python (client d'intégration)

**Vision :** Un package Python `agentforge-sdk` qui permet à n'importe quel développeur d'embarquer des agents AgentForge dans son projet.

**Fichiers :**
- Créer : `sdk/python/agentforge_sdk/__init__.py`
- Créer : `sdk/python/agentforge_sdk/client.py`
- Créer : `sdk/python/agentforge_sdk/models.py`
- Créer : `sdk/python/pyproject.toml`

- [ ] **Step 8.2.1 — Écrire les tests du SDK**

```python
# sdk/python/tests/test_client.py
from agentforge_sdk import AgentForgeClient

def test_client_initialization():
    client = AgentForgeClient(base_url="http://localhost:8000", api_key="test")
    assert client.base_url == "http://localhost:8000"

def test_run_agent_sync(client, mock_server):
    result = client.agents.run(
        agent_id="uuid-here",
        message="Bonjour, résume ce texte : ...",
    )
    assert result.status in ("completed", "failed")
    assert isinstance(result.output, str)
```

- [ ] **Step 8.2.2 — Créer le client SDK**

Créer `sdk/python/agentforge_sdk/client.py` :

```python
"""AgentForge Python SDK — embed agents in any project."""
import httpx
from dataclasses import dataclass
from typing import Generator


@dataclass
class ExecutionResult:
    id: str
    status: str
    output: str
    token_usage: dict


class AgentsAPI:
    def __init__(self, http: httpx.Client, base_url: str):
        self._http = http
        self._base = base_url

    def run(self, agent_id: str, message: str, thread_id: str | None = None) -> ExecutionResult:
        """Run an agent synchronously and return the result."""
        resp = self._http.post(
            f"{self._base}/api/v1/agents/{agent_id}/execute",
            json={
                "input_messages": [{"role": "user", "content": message}],
                "thread_id": thread_id,
                "run_async": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        output_msgs = data.get("output_messages", [])
        output_text = output_msgs[-1]["content"] if output_msgs else ""
        return ExecutionResult(
            id=data["id"],
            status=data["status"],
            output=output_text,
            token_usage=data.get("token_usage", {}),
        )

    def stream(self, agent_id: str, message: str, thread_id: str | None = None) -> Generator[str, None, None]:
        """Stream agent response token by token."""
        import json
        resp = self._http.post(
            f"{self._base}/api/v1/agents/{agent_id}/execute",
            json={
                "input_messages": [{"role": "user", "content": message}],
                "thread_id": thread_id,
                "run_async": True,
            },
        )
        resp.raise_for_status()
        execution_id = resp.json()["id"]
        with self._http.stream("GET", f"{self._base}/api/v1/agents/{agent_id}/executions/{execution_id}/stream") as stream:
            for line in stream.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("type") == "token":
                        yield data["content"]
                    elif data.get("type") == "done":
                        break

    def export(self, agent_id: str) -> dict:
        """Export agent as portable JSON bundle."""
        resp = self._http.get(f"{self._base}/api/v1/agents/{agent_id}/export")
        resp.raise_for_status()
        return resp.json()

    def import_bundle(self, bundle: dict) -> dict:
        """Import an agent from a JSON bundle."""
        resp = self._http.post(f"{self._base}/api/v1/agents/import", json=bundle)
        resp.raise_for_status()
        return resp.json()


class AgentForgeClient:
    """
    AgentForge Python SDK.

    Usage:
        from agentforge_sdk import AgentForgeClient

        client = AgentForgeClient(
            base_url="https://your-agentforge.com",
            api_key="your-api-key",
        )
        result = client.agents.run(agent_id="...", message="Hello!")
        print(result.output)
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self.agents = AgentsAPI(self._http, self.base_url)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

- [ ] **Step 8.2.3 — Créer le pyproject.toml du SDK**

```toml
# sdk/python/pyproject.toml
[project]
name = "agentforge-sdk"
version = "0.1.0"
description = "Python SDK for AgentForge — embed AI agents in any project"
dependencies = ["httpx>=0.27.0"]
requires-python = ">=3.10"

[project.optional-dependencies]
async = ["httpx[asyncio]>=0.27.0"]
```

- [ ] **Step 8.2.4 — Ajouter un endpoint API Key dans le backend**

Pour permettre l'authentification SDK, créer un endpoint `POST /api/v1/me/api-keys` qui génère des clés d'API longue durée (différentes des JWT). Stocker dans une table `api_keys` (user_id, key_hash, name, last_used_at, expires_at).

- [ ] **Step 8.2.5 — Commit**

```bash
git add sdk/
git commit -m "feat: add Python SDK (agentforge-sdk) for embedding agents in external projects"
```

---

## Checklist de validation finale

- [ ] Les tests backend passent : `cd backend && uv run pytest -v`
- [ ] Le frontend build sans erreurs : `cd frontend && npm run build`
- [ ] Connexion Google OAuth → Gmail + Calendar fonctionne
- [ ] Agent "Secrétaire calendrier" lit les emails et les événements
- [ ] Le Chat UI charge et envoie des messages en SSE
- [ ] L'export JSON d'un agent re-importable dans une autre instance
- [ ] Le SDK Python permet `client.agents.run(agent_id, message)` et retourne une réponse

---

## Ordre d'exécution recommandé

```
Phase 1 (30 min)  → Modèles + nettoyage orphelins
Phase 2 (2-3h)    → Chat UI (impact utilisateur immédiat)
Phase 3 (1-2h)    → Skills + agents par défaut
Phase 4 (1h)      → Contexte utilisateur
Phase 5 (2-3h)    → Google integrations (dépend de Phase 4 pour les tokens)
Phase 6 (1h)      → Playground (sandbox repensée)
Phase 7 (1h)      → Builder UX + Cron UX
Phase 8 (3-4h)    → Import/Export + SDK
```

**Total estimé : 12-18h de développement focalisé.**
