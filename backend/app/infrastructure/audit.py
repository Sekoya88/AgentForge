"""Lightweight audit event logger — fire-and-forget, non-blocking."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

log = logging.getLogger(__name__)


def log_audit_event(
    user_id: UUID | None,
    event_type: str,
    resource_type: str,
    resource_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Schedule an audit log write as a background task. Never raises."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            _write_audit(user_id, event_type, resource_type, resource_id, payload or {})
        )
    except RuntimeError:
        pass  # No event loop — skip silently


async def _write_audit(
    user_id: UUID | None,
    event_type: str,
    resource_type: str,
    resource_id: str | None,
    payload: dict[str, Any],
) -> None:
    try:
        from app.infrastructure.persistence.postgres.models import AuditLogModel
        from app.infrastructure.persistence.postgres.session import session_scope

        async with session_scope() as session:
            entry = AuditLogModel(
                user_id=user_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                payload=payload,
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        log.warning("audit log write failed: %s", e)
