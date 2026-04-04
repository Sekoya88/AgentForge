# Long-Term Agent Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give agents persistent cross-session memory — they can save facts during a conversation and recall them in future sessions, scoped per (user, agent) pair, stored as pgvector embeddings.

**Architecture:** New `MemoryStore` port (abstract interface in domain layer) with a pgvector-backed implementation in infrastructure. Two new graph node types (`memory_save`, `memory_recall`) are registered in the LangGraph orchestrator. A new Alembic migration adds the `agent_memories` table. The agent graph builder UI gets two new draggable nodes. No changes to existing nodes or execution flow.

**Tech Stack:** Python / FastAPI, SQLAlchemy async + pgvector, OpenAI embeddings (text-embedding-3-small, same as RAG), Alembic, React / Next.js 15, `@xyflow/react`.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/domain/ports/memory_store.py` | Create | Abstract `MemoryStore` port |
| `backend/app/domain/entities/memory.py` | Create | `MemoryEntry` dataclass |
| `backend/migrations/versions/xxxx_add_agent_memories.py` | Create | Alembic migration for `agent_memories` table |
| `backend/app/infrastructure/persistence/postgres/models.py` | Modify | Add `AgentMemoryModel` ORM model |
| `backend/app/infrastructure/memory/pgvector_memory_store.py` | Create | pgvector-backed `MemoryStore` implementation |
| `backend/app/infrastructure/orchestration/langgraph_orchestrator.py` | Modify | Register `memory_save` and `memory_recall` node types |
| `backend/app/api/v1/agents.py` | Modify | Inject `MemoryStore` into orchestrator calls |
| `backend/app/api/v1/memory.py` | Create | CRUD endpoints: list/delete memories per agent |
| `backend/tests/unit/test_memory_store.py` | Create | Unit tests for `MemoryStore` logic |
| `frontend/src/app/agents/[id]/builder/page.tsx` | Modify | Add `memory_save` and `memory_recall` to node palette |

---

## Task 1: Define `MemoryEntry` entity and `MemoryStore` port

**Files:**
- Create: `backend/app/domain/entities/memory.py`
- Create: `backend/app/domain/ports/memory_store.py`

- [ ] **Step 1: Create `MemoryEntry` dataclass**

```python
# backend/app/domain/entities/memory.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MemoryEntry:
    id: uuid.UUID
    user_id: uuid.UUID
    agent_id: uuid.UUID
    content: str           # the fact/summary stored
    importance: float      # 0.0–1.0, used for ranking on recall
    created_at: datetime
```

- [ ] **Step 2: Create `MemoryStore` abstract port**

```python
# backend/app/domain/ports/memory_store.py
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.app.domain.entities.memory import MemoryEntry


class MemoryStore(ABC):
    """Port for persistent cross-session agent memory backed by vector search."""

    @abstractmethod
    async def save(
        self,
        user_id: UUID,
        agent_id: UUID,
        content: str,
        embedding: list[float],
        importance: float = 0.5,
    ) -> MemoryEntry:
        """Persist a memory entry and return it."""

    @abstractmethod
    async def recall(
        self,
        user_id: UUID,
        agent_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
    ) -> list[MemoryEntry]:
        """Return the top_k most semantically relevant memories."""

    @abstractmethod
    async def list_all(
        self,
        user_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """Return all memories for a (user, agent) pair, newest first."""

    @abstractmethod
    async def delete(self, memory_id: UUID, user_id: UUID) -> bool:
        """Delete a memory. Returns True if found and deleted."""
```

- [ ] **Step 3: Verify Python imports resolve**

```bash
cd backend && python -c "from app.domain.ports.memory_store import MemoryStore; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
rtk git add backend/app/domain/entities/memory.py backend/app/domain/ports/memory_store.py
rtk git commit -m "feat(memory): add MemoryEntry entity and MemoryStore port"
```

---

## Task 2: Add `AgentMemoryModel` ORM model

**Files:**
- Modify: `backend/app/infrastructure/persistence/postgres/models.py`

- [ ] **Step 1: Add pgvector import and `AgentMemoryModel`**

At the top of `models.py`, add to existing imports:
```python
from pgvector.sqlalchemy import Vector
```

At the end of `models.py`, append:
```python
class AgentMemoryModel(Base):
    __tablename__ = "agent_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Verify model imports**

```bash
cd backend && python -c "from app.infrastructure.persistence.postgres.models import AgentMemoryModel; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
rtk git add backend/app/infrastructure/persistence/postgres/models.py
rtk git commit -m "feat(memory): add AgentMemoryModel ORM model"
```

---

## Task 3: Write and run Alembic migration

**Files:**
- Create: `backend/migrations/versions/xxxx_add_agent_memories.py`

- [ ] **Step 1: Generate the migration**

```bash
cd backend && python -m alembic revision --autogenerate -m "add_agent_memories"
```

Expected: creates a new file in `migrations/versions/` with `agent_memories` table.

- [ ] **Step 2: Verify the generated migration looks correct**

Open the generated file and confirm it contains:
- `CREATE TABLE agent_memories`
- `user_id UUID REFERENCES users(id) ON DELETE CASCADE`
- `agent_id UUID REFERENCES agents(id) ON DELETE CASCADE`
- `embedding vector(1536)`
- `importance FLOAT`

Also add an IVFFLAT index for vector search in the `upgrade()` function:
```python
op.execute("CREATE INDEX ON agent_memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
```

- [ ] **Step 3: Apply migration to dev database**

```bash
cd backend && python -m alembic upgrade head
```

Expected: `Running upgrade ... -> xxxx, add_agent_memories`

- [ ] **Step 4: Commit**

```bash
rtk git add backend/migrations/versions/
rtk git commit -m "feat(memory): add agent_memories migration with ivfflat index"
```

---

## Task 4: Implement `PgvectorMemoryStore`

**Files:**
- Create: `backend/app/infrastructure/memory/pgvector_memory_store.py`

- [ ] **Step 1: Create the implementation**

```python
# backend/app/infrastructure/memory/pgvector_memory_store.py
from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.entities.memory import MemoryEntry
from backend.app.domain.ports.memory_store import MemoryStore
from backend.app.infrastructure.persistence.postgres.models import AgentMemoryModel


class PgvectorMemoryStore(MemoryStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        user_id: UUID,
        agent_id: UUID,
        content: str,
        embedding: list[float],
        importance: float = 0.5,
    ) -> MemoryEntry:
        row = AgentMemoryModel(
            id=uuid.uuid4(),
            user_id=user_id,
            agent_id=agent_id,
            content=content,
            embedding=embedding,
            importance=importance,
        )
        self._session.add(row)
        await self._session.flush()
        return MemoryEntry(
            id=row.id,
            user_id=row.user_id,
            agent_id=row.agent_id,
            content=row.content,
            importance=row.importance,
            created_at=row.created_at,
        )

    async def recall(
        self,
        user_id: UUID,
        agent_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
    ) -> list[MemoryEntry]:
        # Use pgvector cosine distance operator <=>
        stmt = (
            select(AgentMemoryModel)
            .where(
                AgentMemoryModel.user_id == user_id,
                AgentMemoryModel.agent_id == agent_id,
            )
            .order_by(AgentMemoryModel.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            MemoryEntry(
                id=r.id,
                user_id=r.user_id,
                agent_id=r.agent_id,
                content=r.content,
                importance=r.importance,
                created_at=r.created_at,
            )
            for r in rows
        ]

    async def list_all(
        self,
        user_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        stmt = (
            select(AgentMemoryModel)
            .where(
                AgentMemoryModel.user_id == user_id,
                AgentMemoryModel.agent_id == agent_id,
            )
            .order_by(AgentMemoryModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            MemoryEntry(
                id=r.id,
                user_id=r.user_id,
                agent_id=r.agent_id,
                content=r.content,
                importance=r.importance,
                created_at=r.created_at,
            )
            for r in rows
        ]

    async def delete(self, memory_id: UUID, user_id: UUID) -> bool:
        stmt = delete(AgentMemoryModel).where(
            AgentMemoryModel.id == memory_id,
            AgentMemoryModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
```

- [ ] **Step 2: Write unit tests**

```python
# backend/tests/unit/test_memory_store.py
"""Unit tests for PgvectorMemoryStore using an in-memory mock session."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.domain.entities.memory import MemoryEntry
from backend.app.infrastructure.memory.pgvector_memory_store import PgvectorMemoryStore


def _make_row(user_id: uuid.UUID, agent_id: uuid.UUID, content: str) -> MagicMock:
    row = MagicMock()
    row.id = uuid.uuid4()
    row.user_id = user_id
    row.agent_id = agent_id
    row.content = content
    row.importance = 0.5
    row.created_at = datetime.now(tz=timezone.utc)
    return row


@pytest.mark.asyncio
async def test_save_returns_memory_entry():
    session = AsyncMock()
    session.flush = AsyncMock()
    store = PgvectorMemoryStore(session)

    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    # Patch AgentMemoryModel so we can inspect what was added
    with patch("backend.app.infrastructure.memory.pgvector_memory_store.AgentMemoryModel") as MockModel:
        instance = _make_row(user_id, agent_id, "Paris is the capital of France")
        MockModel.return_value = instance

        entry = await store.save(
            user_id=user_id,
            agent_id=agent_id,
            content="Paris is the capital of France",
            embedding=[0.1] * 1536,
        )

    assert isinstance(entry, MemoryEntry)
    assert entry.content == "Paris is the capital of France"
    assert entry.user_id == user_id
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_returns_true_when_found():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.rowcount = 1
    session.execute = AsyncMock(return_value=result_mock)

    store = PgvectorMemoryStore(session)
    deleted = await store.delete(uuid.uuid4(), uuid.uuid4())

    assert deleted is True


@pytest.mark.asyncio
async def test_delete_returns_false_when_not_found():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.rowcount = 0
    session.execute = AsyncMock(return_value=result_mock)

    store = PgvectorMemoryStore(session)
    deleted = await store.delete(uuid.uuid4(), uuid.uuid4())

    assert deleted is False
```

- [ ] **Step 3: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_memory_store.py -v
```

Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
rtk git add backend/app/infrastructure/memory/ backend/tests/unit/test_memory_store.py
rtk git commit -m "feat(memory): implement PgvectorMemoryStore with unit tests"
```

---

## Task 5: Add `memory_save` and `memory_recall` node types to orchestrator

**Files:**
- Modify: `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`

The orchestrator's `_build_step` function dispatches on `ntype`. We add two new branches.

- [ ] **Step 1: Add `memory_save` node type**

In `_build_step`, find the `if ntype == "tool":` branch. Before it, add:

```python
if ntype == "memory_save":
    cfg = spec.get("config") or {}
    importance = float(cfg.get("importance", 0.5))

    async def _memory_save_step(state: _State, _node_id=node_id, _importance=importance):
        t0 = time.perf_counter()
        await bus.emit("agent_start", {"agent_name": _node_id, "node_type": "memory_save", "input_preview": ""})
        # Extract last assistant message as the content to save
        last_ai = next(
            (m for m in reversed(state["messages"]) if hasattr(m, "content") and not hasattr(m, "tool_calls")),
            None,
        )
        content = str(last_ai.content) if last_ai else ""
        if content and memory_store is not None and openai_key:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=openai_key)
            resp = await client.embeddings.create(model="text-embedding-3-small", input=content)
            embedding = resp.data[0].embedding
            await memory_store.save(
                user_id=state.get("user_id"),
                agent_id=state.get("agent_id"),
                content=content,
                embedding=embedding,
                importance=_importance,
            )
        dur = int((time.perf_counter() - t0) * 1000)
        await bus.emit("agent_end", {"agent_name": _node_id, "duration_ms": dur, "output_preview": f"saved {len(content)} chars"})
        return {}

    return _memory_save_step

if ntype == "memory_recall":
    cfg = spec.get("config") or {}
    top_k = int(cfg.get("top_k", 5))

    async def _memory_recall_step(state: _State, _node_id=node_id, _top_k=top_k):
        t0 = time.perf_counter()
        await bus.emit("agent_start", {"agent_name": _node_id, "node_type": "memory_recall", "input_preview": ""})
        memories: list[str] = []
        if memory_store is not None and openai_key:
            # Use the last user message as the recall query
            last_human = next(
                (m for m in reversed(state["messages"]) if getattr(m, "type", "") == "human"),
                None,
            )
            query = str(last_human.content) if last_human else ""
            if query:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=openai_key)
                resp = await client.embeddings.create(model="text-embedding-3-small", input=query)
                embedding = resp.data[0].embedding
                entries = await memory_store.recall(
                    user_id=state.get("user_id"),
                    agent_id=state.get("agent_id"),
                    query_embedding=embedding,
                    top_k=_top_k,
                )
                memories = [e.content for e in entries]

        # Inject memories as a system message so the LLM sees them
        memory_block = "\n".join(f"- {m}" for m in memories)
        injection = f"[Relevant memories from previous sessions]\n{memory_block}" if memories else ""
        from langchain_core.messages import SystemMessage
        new_msgs = [SystemMessage(content=injection)] if injection else []
        dur = int((time.perf_counter() - t0) * 1000)
        await bus.emit("agent_end", {"agent_name": _node_id, "duration_ms": dur, "output_preview": f"recalled {len(memories)} memories"})
        return {"messages": new_msgs}

    return _memory_recall_step
```

- [ ] **Step 2: Add `memory_store` parameter to `_build_step` signature**

Find the function signature of `_build_step` and add:
```python
memory_store: "MemoryStore | None" = None,
```

- [ ] **Step 3: Add `memory_store` to the `_State` TypedDict**

Find the `_State` TypedDict definition and add:
```python
user_id: uuid.UUID | None
agent_id: uuid.UUID | None
```

- [ ] **Step 4: Thread `memory_store` through orchestrator call sites**

In the orchestrator's `run()` or `execute()` method (wherever `_build_step` is called), pass `memory_store=memory_store` from the method arguments.

- [ ] **Step 5: Verify Python syntax**

```bash
cd backend && python -c "from app.infrastructure.orchestration.langgraph_orchestrator import _build_step; print('ok')" 2>&1 | head -10
```

- [ ] **Step 6: Commit**

```bash
rtk git add backend/app/infrastructure/orchestration/langgraph_orchestrator.py
rtk git commit -m "feat(memory): add memory_save and memory_recall node types to orchestrator"
```

---

## Task 6: Add memory API endpoints

**Files:**
- Create: `backend/app/api/v1/memory.py`

- [ ] **Step 1: Create the router**

```python
# backend/app/api/v1/memory.py
from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_db
from backend.app.domain.entities.user import User
from backend.app.infrastructure.memory.pgvector_memory_store import PgvectorMemoryStore

router = APIRouter(prefix="/api/v1/agents/{agent_id}/memories", tags=["memory"])


class MemoryOut(BaseModel):
    id: UUID
    content: str
    importance: float
    created_at: str

    @classmethod
    def from_entry(cls, entry) -> "MemoryOut":
        return cls(
            id=entry.id,
            content=entry.content,
            importance=entry.importance,
            created_at=entry.created_at.isoformat(),
        )


@router.get("/", response_model=list[MemoryOut])
async def list_memories(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    store = PgvectorMemoryStore(db)
    entries = await store.list_all(current_user.id, agent_id)
    return [MemoryOut.from_entry(e) for e in entries]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    agent_id: UUID,
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    store = PgvectorMemoryStore(db)
    deleted = await store.delete(memory_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
```

- [ ] **Step 2: Register router in main app**

In `backend/app/main.py` (or wherever routers are registered), add:
```python
from backend.app.api.v1 import memory as memory_router
app.include_router(memory_router.router)
```

- [ ] **Step 3: Verify app starts**

```bash
cd backend && python -c "from app.main import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
rtk git add backend/app/api/v1/memory.py backend/app/main.py
rtk git commit -m "feat(memory): add GET/DELETE memory API endpoints"
```

---

## Task 7: Add `memory_save` and `memory_recall` nodes to graph builder UI

**Files:**
- Modify: `frontend/src/app/agents/[id]/builder/page.tsx`

- [ ] **Step 1: Find the node type palette**

Search for where existing node types are defined for the palette (look for `"llm"`, `"tool"`, `"skill"` labels in the builder page).

```bash
rtk grep -n "node_type\|nodeType\|llm.*tool\|palette" frontend/src/app/agents/\[id\]/builder/page.tsx | head -20
```

- [ ] **Step 2: Add memory node types to the palette array**

Find the array of available node types (likely an array of objects with `type`, `label`, `icon` or similar fields) and add:

```typescript
{
  type: "memory_save",
  label: "Memory Save",
  description: "Persiste le dernier message en mémoire longue durée",
  icon: "save",           // Material icon name already used in the project
  color: "#7c3aed",
},
{
  type: "memory_recall",
  label: "Memory Recall",
  description: "Injecte les souvenirs pertinents avant la réponse LLM",
  icon: "psychology",     // Material icon name
  color: "#7c3aed",
},
```

- [ ] **Step 3: Ensure the node schema accepts the new types**

Search for where node type validation happens (likely a Zod schema or a type union):
```bash
rtk grep -n "\"llm\"\|\"tool\"\|\"interrupt\"\|node.*type" frontend/src/app/agents/\[id\]/builder/page.tsx | head -10
```

Add `"memory_save"` and `"memory_recall"` to the union.

- [ ] **Step 4: Verify TypeScript**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 5: Commit**

```bash
rtk git add frontend/src/app/agents/\[id\]/builder/page.tsx
rtk git commit -m "feat(memory): add memory_save and memory_recall nodes to graph builder"
```

---

## Task 8: Final integration check

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```

Expected: all existing tests pass + 3 new memory tests pass.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && rtk npm run build 2>&1 | tail -15
```

Expected: `✓ Compiled successfully`

- [ ] **Step 3: Smoke test: verify memory endpoints exist**

```bash
cd backend && python -c "
from app.main import app
routes = [r.path for r in app.routes]
memory_routes = [r for r in routes if 'memories' in r]
print('Memory routes:', memory_routes)
assert memory_routes, 'No memory routes found!'
print('ok')
"
```

Expected: prints memory routes and `ok`.

- [ ] **Step 4: Final commit**

```bash
rtk git add -A
rtk git commit -m "feat(memory): complete long-term agent memory — save, recall, list, delete"
```
