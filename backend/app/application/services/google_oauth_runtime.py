"""Resolve Google OAuth access token (+ scopes) for agent executions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.infrastructure.auth.google_oauth_flow import refresh_access_token_with_refresh
from app.infrastructure.auth.token_cipher import (
    decrypt_optional,
    encrypt_optional,
    fernet_from_settings,
)
from app.infrastructure.persistence.postgres.models import SocialAccountModel


@dataclass(frozen=True)
class GoogleOAuthRuntime:
    access_token: str
    scopes: frozenset[str]


async def resolve_google_oauth_runtime(
    session: AsyncSession,
    user_id: UUID,
    *,
    settings: Settings | None = None,
) -> GoogleOAuthRuntime | None:
    settings = settings or get_settings()
    q = await session.execute(
        select(SocialAccountModel).where(
            SocialAccountModel.user_id == user_id,
            SocialAccountModel.provider == "google",
        )
    )
    row = q.scalar_one_or_none()
    if row is None or not row.access_token_cipher:
        return None
    fernet = fernet_from_settings(settings)
    access = decrypt_optional(fernet, row.access_token_cipher)
    if not access:
        return None
    refresh = decrypt_optional(fernet, row.refresh_token_cipher)
    now = datetime.now(UTC)
    exp = row.expires_at
    needs_refresh = False
    if exp is not None:
        exp_aware = exp if exp.tzinfo else exp.replace(tzinfo=UTC)
        needs_refresh = now >= exp_aware - timedelta(seconds=90)
    if needs_refresh and refresh:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                data = await refresh_access_token_with_refresh(settings, refresh, client=client)
            new_access = data.get("access_token")
            if isinstance(new_access, str) and new_access:
                enc_access = encrypt_optional(fernet, new_access)
                expires_in = data.get("expires_in")
                new_exp = None
                if isinstance(expires_in, int):
                    new_exp = now + timedelta(seconds=expires_in)
                await session.execute(
                    update(SocialAccountModel)
                    .where(SocialAccountModel.id == row.id)
                    .values(
                        access_token_cipher=enc_access,
                        expires_at=new_exp,
                    )
                )
                await session.commit()
                access = new_access
        except Exception:
            pass
    scope_list = list(row.scopes or []) if row.scopes is not None else []
    return GoogleOAuthRuntime(access_token=access, scopes=frozenset(scope_list))
