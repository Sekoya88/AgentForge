"""Background tick: run agent schedules whose next_run_at is due."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.application.services.agent_service import AgentService
from app.dependencies import build_agent_service_for_worker
from app.domain.schedule_cron import next_fire_after
from app.infrastructure.persistence.postgres.agent_repo import PostgresAgentRepository
from app.infrastructure.persistence.postgres.session import session_scope
from app.infrastructure.webhooks.delivery import schedule_schedule_fired_webhook

log = logging.getLogger(__name__)

SCHEDULE_TICK_INTERVAL_SEC = 60
SCHEDULE_INITIAL_DELAY_SEC = 5


async def run_schedule_tick_once() -> None:
    now = datetime.now(UTC)
    claimed: list[tuple[UUID, UUID, dict[str, Any], str | None, UUID]] = []

    async with session_scope() as session:
        repo = PostgresAgentRepository(session)
        due = await repo.list_due_schedules(now, limit=50)
        for sch in due:
            if sch.user_id is None:
                continue
            nxt = next_fire_after(sch.cron_expression, now)
            await repo.update_schedule_run_times(
                sch.id,
                last_run_at=now,
                next_run_at=nxt,
            )
            claimed.append((sch.agent_id, sch.user_id, sch.input, sch.alias, sch.id))

    for agent_id, user_id, input_payload, alias, schedule_id in claimed:
        raw_msgs = input_payload.get("input_messages")
        if not raw_msgs:
            raw_msgs = [{"role": "user", "content": "Scheduled run."}]
        schedule_schedule_fired_webhook(
            user_id,
            {
                "agent_id": str(agent_id),
                "schedule_id": str(schedule_id),
                "fired_at": now.isoformat(),
            },
        )
        try:
            async with session_scope() as session:
                svc: AgentService = build_agent_service_for_worker(session)
                use_async = svc._redis is not None
                await svc.execute(
                    agent_id,
                    user_id,
                    raw_msgs,
                    run_async=use_async,
                    alias=alias,
                    trigger_source="schedule",
                    schedule_id=schedule_id,
                )
        except Exception:
            log.exception(
                "scheduled_execution_failed",
                extra={
                    "agent_id": str(agent_id),
                    "schedule_id": str(schedule_id),
                },
            )


async def schedule_worker_loop(stop: asyncio.Event) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=SCHEDULE_INITIAL_DELAY_SEC)
        return
    except TimeoutError:
        pass
    while not stop.is_set():
        try:
            await run_schedule_tick_once()
        except Exception:
            log.exception("schedule_tick_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=SCHEDULE_TICK_INTERVAL_SEC)
        except TimeoutError:
            continue
        return
