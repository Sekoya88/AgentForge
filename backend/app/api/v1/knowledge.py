from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.schemas.knowledge_schemas import (
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeSourceOut,
)
from app.application.services.knowledge_service import KnowledgeService
from app.dependencies import get_current_user, get_knowledge_service
from app.domain.entities.user import User

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_ALLOWED_UPLOAD_SUFFIXES = frozenset({".txt", ".md", ".csv"})


@router.get("/sources", response_model=list[KnowledgeSourceOut])
async def list_sources(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> list[KnowledgeSourceOut]:
    rows = await svc.list_sources(user.id)
    return [KnowledgeSourceOut(title=r.title, chunk_count=r.chunk_count) for r in rows]


@router.post("/ingest", response_model=KnowledgeIngestResponse)
async def ingest(
    body: KnowledgeIngestRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeIngestResponse:
    try:
        out = await svc.ingest_text(user.id, body.title, body.text)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error: {e!s}",
        ) from e
    return KnowledgeIngestResponse(title=out["title"], chunks=out["chunks"])


@router.post("/upload", response_model=KnowledgeIngestResponse)
async def upload(
    file: UploadFile,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeIngestResponse:
    name = file.filename or ""
    suffix = Path(name).suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt, .md, and .csv files are allowed",
        )
    title = Path(name).stem or "untitled"
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be valid UTF-8 text",
        ) from e
    try:
        out = await svc.ingest_text(user.id, title, content)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error: {e!s}",
        ) from e
    return KnowledgeIngestResponse(title=out["title"], chunks=out["chunks"])


@router.delete("/sources/{title:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    title: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> None:
    n = await svc.delete_source(user.id, title)
    if n == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown source title")
