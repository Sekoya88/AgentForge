"""Forge Assistant API — direct LLM chat with tool use and multi-conversation support."""

from typing import Annotated
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.sse import redis_stream_sse
from app.dependencies import get_current_user, get_forge_service, get_redis_required
from app.domain.entities.user import User
from app.infrastructure.events.redis_execution_stream import execution_stream_key

router = APIRouter(prefix="/forge", tags=["forge"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class CreateConversationRequest(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    title: str | None = None


class ConversationResponse(BaseModel):
    id: str
    thread_id: str
    title: str | None
    provider: str
    model: str
    created_at: str
    updated_at: str
    last_message_at: str | None
    message_count: int


class ExecuteRequest(BaseModel):
    message: str
    provider: str | None = None
    model: str | None = None


class ExecuteResponse(BaseModel):
    execution_id: str
    conversation_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _conv_resp(conv) -> ConversationResponse:
    return ConversationResponse(
        id=str(conv.id),
        thread_id=conv.thread_id,
        title=conv.title,
        provider=conv.provider,
        model=conv.model,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        last_message_at=conv.last_message_at.isoformat() if conv.last_message_at else None,
        message_count=conv.message_count,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    body: CreateConversationRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc=Depends(get_forge_service),
):
    conv = await svc.create_conversation(user.id, body.provider, body.model, body.title)
    return _conv_resp(conv)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    svc=Depends(get_forge_service),
):
    return [_conv_resp(c) for c in await svc.list_conversations(user.id)]


@router.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(
    conv_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc=Depends(get_forge_service),
) -> list[dict]:
    return await svc.get_messages(user.id, conv_id)


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc=Depends(get_forge_service),
):
    await svc.delete_conversation(user.id, conv_id)


@router.post("/conversations/{conv_id}/execute", response_model=ExecuteResponse)
async def execute(
    conv_id: UUID,
    body: ExecuteRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc=Depends(get_forge_service),
):
    try:
        execution_id = await svc.execute(
            user.id,
            conv_id,
            body.message,
            provider=body.provider,
            model=body.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ExecuteResponse(execution_id=str(execution_id), conversation_id=str(conv_id))


@router.get("/stream/{execution_id}")
async def stream_execution(
    execution_id: UUID,
    r: Annotated[redis.Redis, Depends(get_redis_required)],
    _user: Annotated[User, Depends(get_current_user)],
    after_id: Annotated[
        str | None,
        Query(description="Last Redis stream id received; server skips earlier events"),
    ] = None,
):
    key = execution_stream_key(execution_id)
    return StreamingResponse(
        redis_stream_sse(r, key, resume_after=after_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
