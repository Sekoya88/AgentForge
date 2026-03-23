import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from sse_starlette.sse import EventSourceResponse

from app.api.schemas.finetune_schemas import FinetuneCreateRequest, FinetuneJobResponse
from app.application.services.finetune_service import FinetuneService
from app.dependencies import get_current_user, get_finetune_service, get_redis_optional
from app.domain.entities.user import User

router = APIRouter(prefix="/finetune", tags=["finetune"])


async def _finetune_pubsub_sse(redis_client: aioredis.Redis, channel: str) -> AsyncIterator[dict]:
    """Subscribe to Redis Pub/Sub channel and yield SSE dicts."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    try:
        # Yield a heartbeat immediately so the client knows the stream opened
        yield {"event": "connected", "data": json.dumps({"channel": channel})}
        while True:
            msg = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True), timeout=25
            )
            if msg is None:
                yield {"event": "ping", "data": ""}
                continue
            raw = msg.get("data", b"")
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                payload = {"data": raw}
            event_type = payload.get("type", "metrics")
            if event_type in ("completed", "failed", "cancelled"):
                yield {"event": event_type, "data": json.dumps(payload)}
                return
            yield {"event": event_type, "data": json.dumps(payload)}
    except TimeoutError:
        yield {"event": "ping", "data": ""}
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


@router.post("", response_model=FinetuneJobResponse, status_code=status.HTTP_201_CREATED)
async def create_finetune_job(
    body: FinetuneCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> FinetuneJobResponse:
    j = await svc.create(user.id, body.base_model, body.dataset_path, body.hyperparams)
    return FinetuneJobResponse.from_entity(j)


@router.get("", response_model=list[FinetuneJobResponse])
async def list_finetune_jobs(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> list[FinetuneJobResponse]:
    items = await svc.list_jobs(user.id)
    return [FinetuneJobResponse.from_entity(j) for j in items]


@router.get("/{job_id}", response_model=FinetuneJobResponse)
async def get_finetune_job(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> FinetuneJobResponse:
    j = await svc.get(UUID(job_id), user.id)
    return FinetuneJobResponse.from_entity(j)


@router.post("/{job_id}/deploy", response_model=FinetuneJobResponse)
async def deploy_finetune(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> FinetuneJobResponse:
    j = await svc.deploy(UUID(job_id), user.id)
    return FinetuneJobResponse.from_entity(j)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_finetune_job(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> None:
    await svc.delete(UUID(job_id), user.id)


@router.delete("/{job_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_finetune_job(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> None:
    await svc.cancel(UUID(job_id), user.id)


@router.get("/{job_id}/stream")
async def stream_finetune_job(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
    redis_client: Annotated[aioredis.Redis | None, Depends(get_redis_optional)] = None,
) -> EventSourceResponse:
    """SSE stream for a fine-tuning job. Subscribes to Redis Pub/Sub channel finetune:{job_id}."""
    # Verify job exists and belongs to user
    await svc.get(UUID(job_id), user.id)

    if redis_client is None:

        async def _no_redis() -> AsyncIterator[dict]:
            yield {"event": "error", "data": json.dumps({"message": "Redis not configured"})}

        return EventSourceResponse(_no_redis(), media_type="text/event-stream")

    channel = f"finetune:{job_id}"
    return EventSourceResponse(
        _finetune_pubsub_sse(redis_client, channel),
        media_type="text/event-stream",
    )
