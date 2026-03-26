import asyncio
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated
from uuid import UUID

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.api.schemas.finetune_schemas import FinetuneCreateRequest, FinetuneJobResponse
from app.application.services.finetune_service import FinetuneService
from app.config import Settings
from app.dependencies import (
    get_current_user,
    get_finetune_service,
    get_redis_optional,
    get_settings_dep,
)
from app.domain.entities.user import User


class InferenceStreamRequest(BaseModel):
    prompt: str
    max_new_tokens: int = 128
    temperature: float = 0.7


DATASET_DIR = Path(__file__).resolve().parents[3] / "datasets"

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


@router.get("/deployed", response_model=list[FinetuneJobResponse])
async def list_deployed_models(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> list[FinetuneJobResponse]:
    """List completed fine-tune jobs that have inference endpoints (usable as agent providers)."""
    jobs = await svc.list_jobs(user.id)
    deployed = [j for j in jobs if j.status == "completed" and j.inference_endpoint]
    return [FinetuneJobResponse.from_entity(j) for j in deployed]


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


@router.post("/{job_id}/evaluate")
async def evaluate_finetune(
    job_id: str,
    body: dict,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> dict:
    """Run evaluation prompts against a deployed fine-tuned model."""
    j = await svc.get(UUID(job_id), user.id)
    if j.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed to evaluate")
    if not j.inference_endpoint:
        raise HTTPException(status_code=400, detail="Deploy the model first before evaluating")

    prompts = body.get("prompts", [])
    if not prompts:
        raise HTTPException(status_code=400, detail="prompts list is required")

    import httpx

    # Call the evaluate endpoint on Modal
    settings = svc._settings
    eval_url = (j.inference_endpoint or "").replace("/generate", "/evaluate")
    if not eval_url.endswith("/evaluate"):
        # Fallback: construct from MODAL_INFERENCE_URL
        base = getattr(settings, "modal_inference_url", "") or ""
        eval_url = base.replace("generate", "evaluate")

    if not eval_url:
        raise HTTPException(status_code=400, detail="Cannot determine evaluate endpoint URL")

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            eval_url,
            json={
                "job_id": str(j.id),
                "prompts": prompts[:20],
                "max_new_tokens": int(body.get("max_tokens", 128)),
                "temperature": float(body.get("temperature", 0.1)),
            },
        )
        resp.raise_for_status()
        return resp.json()


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


@router.post("/{job_id}/inference-stream")
async def inference_stream(
    job_id: str,
    body: InferenceStreamRequest,
    current_user: User = Depends(get_current_user),
    settings: Annotated[Settings, Depends(get_settings_dep)] = ...,
):
    """Proxy streaming tokens from Modal inference endpoint."""
    modal_url = settings.modal_inference_url
    if not modal_url:
        raise HTTPException(status_code=503, detail="Modal inference not configured")

    # Modal asgi_app generates a separate URL: replace /generate with /generate-stream
    stream_url = modal_url.replace("/generate", "/generate-stream/")

    payload = {
        "job_id": job_id,
        "prompt": body.prompt,
        "max_new_tokens": body.max_new_tokens,
        "temperature": body.temperature,
    }

    async def _proxy():
        async with httpx.AsyncClient(timeout=120.0) as http:
            async with http.stream("POST", stream_url, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        yield line + "\n\n"

    return StreamingResponse(
        _proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ─── Dataset management ──────────────────────────────────────────────────────

_ALLOWED_EXTS = frozenset({".json", ".jsonl", ".csv", ".parquet"})


@router.post("/datasets/upload", status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Upload a dataset file (JSON, JSONL, CSV, Parquet) for fine-tuning."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {ext}. Allowed: {', '.join(sorted(_ALLOWED_EXTS))}",
        )

    user_dir = DATASET_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    dest = user_dir / safe_name

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(status_code=400, detail="File too large (max 100MB)")

    dest.write_bytes(content)

    # Count rows for preview
    row_count = 0
    preview: list[str] = []
    try:
        if ext in (".json", ".jsonl"):
            lines = content.decode("utf-8", errors="replace").strip().splitlines()
            row_count = len(lines)
            preview = lines[:3]
        elif ext == ".csv":
            lines = content.decode("utf-8", errors="replace").strip().splitlines()
            row_count = max(0, len(lines) - 1)  # minus header
            preview = lines[:4]
    except Exception:
        pass

    return {
        "filename": safe_name,
        "path": str(dest),
        "size_bytes": len(content),
        "rows": row_count,
        "preview": preview,
    }


@router.get("/datasets")
async def list_datasets(
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    """List uploaded datasets for the current user."""
    user_dir = DATASET_DIR / str(user.id)
    if not user_dir.exists():
        return []

    datasets = []
    for f in sorted(user_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in _ALLOWED_EXTS:
            datasets.append(
                {
                    "filename": f.name,
                    "path": str(f),
                    "size_bytes": f.stat().st_size,
                    "ext": f.suffix.lower(),
                }
            )
    return datasets


@router.delete("/datasets/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    filename: str,
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete an uploaded dataset."""
    user_dir = DATASET_DIR / str(user.id)
    safe = filename.replace("/", "_").replace("\\", "_")
    target = user_dir / safe
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Dataset not found")
    os.remove(target)
