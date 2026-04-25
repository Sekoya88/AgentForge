"""Speech-related API (deployed jobs, voice samples for TTS training)."""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from app.api.middleware.rate_limit import limiter
from app.api.schemas.finetune_schemas import FinetuneJobResponse
from app.api.schemas.speech_schemas import VoiceSampleCreatedResponse, VoiceSampleListItem
from app.application.services.finetune_service import FinetuneService
from app.dependencies import (
    get_current_user,
    get_finetune_service,
    get_s3_audio_store,
    get_voice_sample_repository,
)
from app.domain.entities.user import User
from app.infrastructure.persistence.postgres.voice_sample_repo import PostgresVoiceSampleRepository
from app.infrastructure.storage.s3_store import S3AudioStore

router = APIRouter(prefix="/speech", tags=["speech"])

_SPEECH_MODALITIES = frozenset({"whisper", "tts_voice"})
_MAX_VOICE_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get("/deployed", response_model=list[FinetuneJobResponse])
async def list_deployed_speech_models(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> list[FinetuneJobResponse]:
    """Jobs with speech modality, completed, and an inference URL (Modal / HTTP).

    Use ``inference_endpoint`` as ``endpoint_url`` on graph nodes ``finetuned_whisper`` /
    ``finetuned_tts``. Until Modal speech training ships, this list is often empty.
    """
    jobs = await svc.list_jobs(user.id)
    deployed = [
        j
        for j in jobs
        if j.modality in _SPEECH_MODALITIES
        and j.status == "completed"
        and (j.inference_endpoint or "").strip()
    ]
    return [FinetuneJobResponse.from_entity(j) for j in deployed]


@router.post(
    "/voice-samples",
    response_model=VoiceSampleCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/hour")
async def create_voice_sample(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[PostgresVoiceSampleRepository, Depends(get_voice_sample_repository)],
    s3: Annotated[S3AudioStore, Depends(get_s3_audio_store)],
    file: UploadFile = File(...),
    label: str = Form(default=""),
) -> VoiceSampleCreatedResponse:
    """Upload a voice audio file.

    When S3 is configured the raw bytes are stored in object storage and only
    the key is persisted in PostgreSQL.  Without S3 the audio is stored inline
    as base64 (legacy/dev behaviour).
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(raw) > _MAX_VOICE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {_MAX_VOICE_UPLOAD_BYTES} bytes)",
        )

    meta = {"filename": file.filename or ""}

    if s3.enabled:
        ext = (file.filename or "bin").rsplit(".", 1)[-1] or "bin"
        key = await s3.upload(raw, prefix="voice-samples", ext=ext)
        created = await repo.create(
            user.id,
            audio_url=key,
            label=label.strip() or None,
            metadata=meta,
        )
        return VoiceSampleCreatedResponse.from_entity(created, audio_bytes=len(raw))
    else:
        b64 = base64.b64encode(raw).decode("ascii")
        created = await repo.create(
            user.id,
            audio_b64=b64,
            label=label.strip() or None,
            metadata=meta,
        )
        return VoiceSampleCreatedResponse.from_entity(created)


@router.get("/voice-samples", response_model=list[VoiceSampleListItem])
async def list_voice_samples(
    user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[PostgresVoiceSampleRepository, Depends(get_voice_sample_repository)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[VoiceSampleListItem]:
    """List uploaded voice samples (metadata only; no inline base64 to keep payloads small)."""
    rows = await repo.list_for_user(user.id, limit=limit)
    return [VoiceSampleListItem.from_entity(v) for v in rows]
