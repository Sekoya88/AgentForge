"""System settings — read-only info about configuration state."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.dependencies import get_current_user
from app.domain.entities.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


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


def _redact(url: str) -> str:
    """Show host/db but mask password."""
    if "@" not in url:
        return url
    prefix, rest = url.rsplit("@", 1)
    proto = prefix.split("://", 1)[0] if "://" in prefix else "***"
    return f"{proto}://***@{rest}"
