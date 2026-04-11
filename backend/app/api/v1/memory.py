"""Agent memory endpoints — list and delete per-agent memories."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dependencies import get_current_user, get_session, get_settings_dep
from app.domain.entities.user import User
from app.infrastructure.memory.noop_memory_store import NoopMemoryStore
from app.infrastructure.memory.pgvector_memory_store import PgvectorMemoryStore

router = APIRouter(prefix="/agents/{agent_id}/memories", tags=["memory"])


def _memory_store(session: AsyncSession, settings: Settings):
    if settings.disable_pgvector_memory:
        return NoopMemoryStore()
    return PgvectorMemoryStore(session)


class MemoryOut(BaseModel):
    id: UUID
    content: str
    importance: float
    created_at: str


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    limit: int = 100,
) -> list[MemoryOut]:
    store = _memory_store(session, settings)
    entries = await store.list_all(user.id, agent_id, limit=limit)
    return [
        MemoryOut(
            id=e.id,
            content=e.content,
            importance=e.importance,
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    agent_id: UUID,
    memory_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> None:
    if settings.disable_pgvector_memory:
        return
    store = PgvectorMemoryStore(session)
    deleted = await store.delete(memory_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
