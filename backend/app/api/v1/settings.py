"""System settings — read-only info about configuration state."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.secrets_service import SecretsService
from app.config import get_settings
from app.dependencies import get_current_user, get_secrets_service, get_session
from app.domain.entities.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


class SecretsUpdateRequest(BaseModel):
    openai_key: str | None = None
    google_key: str | None = None
    anthropic_key: str | None = None
    tavily_key: str | None = None
    hf_token: str | None = None
    elevenlabs_key: str | None = None


@router.get("/secrets")
async def get_secrets(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, bool]:
    secrets = await svc.get_decrypted_secrets(user.id)
    return {
        "has_openai_key": bool(secrets["openai_key"]),
        "has_google_key": bool(secrets["google_key"]),
        "has_anthropic_key": bool(secrets.get("anthropic_key")),
        "has_tavily_key": bool(secrets.get("tavily_key")),
        "has_hf_token": bool(secrets.get("hf_token")),
        "has_elevenlabs_key": bool(secrets.get("elevenlabs_key")),
    }


@router.put("/secrets", status_code=status.HTTP_204_NO_CONTENT)
async def update_secrets(
    body: SecretsUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SecretsService, Depends(get_secrets_service)],
) -> None:
    await svc.update_secrets(
        user.id,
        body.openai_key,
        body.google_key,
        body.anthropic_key,
        body.tavily_key,
        body.hf_token,
        body.elevenlabs_key,
    )


@router.get("")
async def system_settings(
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    s = get_settings()
    return {
        "sandbox_mode": s.sandbox_mode,
        "redteam_mode": s.redteam_mode,
        "openai_configured": bool(s.openai_api_key),
        "langfuse_configured": bool(getattr(s, "langfuse_public_key", None)),
        "sentry_configured": bool(getattr(s, "sentry_dsn", None)),
        "cors_origins": s.cors_origins,
        "database_url_redacted": _redact(s.database_url),
        "redis_available": bool(getattr(s, "redis_url", None)),
    }


@router.get("/audit", tags=["audit"])
async def list_audit_log(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    event_type: Annotated[str | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    from sqlalchemy import desc, select

    from app.infrastructure.persistence.postgres.models import AuditLogModel

    q = select(AuditLogModel).where(AuditLogModel.user_id == user.id)
    if event_type:
        q = q.where(AuditLogModel.event_type == event_type)
    if resource_type:
        q = q.where(AuditLogModel.resource_type == resource_type)
    q = q.order_by(desc(AuditLogModel.created_at)).limit(limit).offset(offset)
    result = await session.execute(q)
    rows = result.scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "payload": r.payload,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": len(rows),
    }


def _redact(url: str) -> str:
    """Show host/db but mask password."""
    if "@" not in url:
        return url
    prefix, rest = url.rsplit("@", 1)
    proto = prefix.split("://", 1)[0] if "://" in prefix else "***"
    return f"{proto}://***@{rest}"
