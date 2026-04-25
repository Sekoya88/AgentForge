"""Fire-and-forget HTTP webhooks for execution and campaign lifecycle events."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any
from uuid import UUID

import httpx

from app.infrastructure.persistence.postgres.session import session_scope
from app.infrastructure.persistence.postgres.webhook_repo import PostgresWebhookRepository

log = logging.getLogger(__name__)


def _schedule(user_id: UUID, event: str, payload: dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_deliver(user_id, event, payload))


def schedule_execution_completed_webhook(user_id: UUID, payload: dict[str, Any]) -> None:
    _schedule(user_id, "execution.completed", payload)


def schedule_execution_started_webhook(user_id: UUID, payload: dict[str, Any]) -> None:
    _schedule(user_id, "execution.started", payload)


def schedule_execution_failed_webhook(user_id: UUID, payload: dict[str, Any]) -> None:
    _schedule(user_id, "execution.failed", payload)


def schedule_campaign_completed_webhook(user_id: UUID, payload: dict[str, Any]) -> None:
    _schedule(user_id, "campaign.completed", payload)


def schedule_schedule_fired_webhook(user_id: UUID, payload: dict[str, Any]) -> None:
    _schedule(user_id, "schedule.fired", payload)


def schedule_finetune_completed_webhook(user_id: UUID, payload: dict[str, Any]) -> None:
    _schedule(user_id, "finetune.completed", payload)


def schedule_agent_updated_webhook(user_id: UUID, payload: dict[str, Any]) -> None:
    _schedule(user_id, "agent.updated", payload)


async def _deliver(user_id: UUID, event: str, payload: dict[str, Any]) -> None:
    try:
        async with session_scope() as session:
            repo = PostgresWebhookRepository(session)
            endpoints = await repo.list_active_for_user_event(user_id, event)
        body_obj = {"event": event, "payload": payload}
        raw = json.dumps(body_obj, default=str, separators=(",", ":")).encode("utf-8")
        async with httpx.AsyncClient(timeout=15.0) as client:
            for ep in endpoints:
                headers = {"Content-Type": "application/json"}
                if ep.secret:
                    sig = hmac.new(
                        ep.secret.encode("utf-8"),
                        raw,
                        hashlib.sha256,
                    ).hexdigest()
                    headers["X-AgentForge-Signature"] = f"sha256={sig}"
                try:
                    r = await client.post(ep.url, content=raw, headers=headers)
                    r.raise_for_status()
                except Exception:
                    log.exception(
                        "webhook_post_failed",
                        extra={"webhook_id": str(ep.id), "event": event},
                    )
    except Exception:
        log.exception("webhook_delivery_batch_failed", extra={"event": event})
