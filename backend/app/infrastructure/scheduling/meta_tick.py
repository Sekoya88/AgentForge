"""Every 6h: run MetaAgent for users with recent low-scored executions."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func as sa_func
from sqlalchemy import select

from app.infrastructure.persistence.postgres.forge_subagent_repo import ForgeSubAgentRepository
from app.infrastructure.persistence.postgres.models import ExecutionFeedbackModel
from app.infrastructure.persistence.postgres.session import session_scope
from app.infrastructure.subagents.registry import SubAgentRegistry
from app.infrastructure.subagents.runner import SubAgentRunner

log = logging.getLogger(__name__)

META_TICK_INTERVAL_SEC = 3600 * 6  # 6 hours


async def run_meta_tick_once() -> None:
    now = datetime.now(UTC)
    since = now - timedelta(hours=24)

    async with session_scope() as session:
        result = await session.execute(
            select(ExecutionFeedbackModel.user_id)
            .where(
                ExecutionFeedbackModel.created_at >= since,
                ExecutionFeedbackModel.score <= 0.5,
            )
            .group_by(ExecutionFeedbackModel.user_id)
            .having(sa_func.count() >= 3)
        )
        user_ids = [row[0] for row in result.all()]

    for user_id in user_ids:
        try:
            await _run_meta_for_user(user_id)
        except Exception:
            log.exception("meta_tick_user_error", extra={"user_id": str(user_id)})


async def _run_meta_for_user(user_id) -> None:
    async with session_scope() as session:
        from app.application.services.secrets_service import SecretsService
        from app.infrastructure.persistence.postgres.user_secrets_repo import (
            PostgresUserSecretsRepository,
        )

        secrets_svc = SecretsService(PostgresUserSecretsRepository(session))
        secrets = await secrets_svc.get_decrypted_secrets(user_id)
        anthropic_key = secrets.get("anthropic_key")

        if not anthropic_key:
            log.debug("meta_tick_skipped_no_key", extra={"user_id": str(user_id)})
            return

        repo = ForgeSubAgentRepository(session)
        registry = SubAgentRegistry(repo)

        runner = SubAgentRunner(
            registry=registry,
            session=session,
            user_id=user_id,
            anthropic_key=anthropic_key,
        )
        result = await runner.run(
            agent_name="meta_agent",
            task=(
                "Analyse all recent failed and low-scored executions for this user. "
                "Identify patterns. Create up to 5 improvement proposals."
            ),
        )
        log.info(
            "meta_tick_complete",
            extra={"user_id": str(user_id), "summary": result.get("summary", "")},
        )

        await _post_to_forge_conversation(session, user_id, result.get("summary", ""))


async def _post_to_forge_conversation(session, user_id, summary: str) -> None:
    """Append a MetaAgent report to the user's most recent Forge conversation."""
    import uuid as uuid_mod

    from sqlalchemy import desc

    from app.infrastructure.persistence.postgres.models import (
        ForgeConversationModel,
        ForgeExecutionModel,
    )

    result = await session.execute(
        select(ForgeConversationModel)
        .where(ForgeConversationModel.user_id == user_id)
        .order_by(desc(ForgeConversationModel.last_message_at))
        .limit(1)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        return

    row = ForgeExecutionModel(
        id=uuid_mod.uuid4(),
        user_id=user_id,
        conversation_id=conv.id,
        thread_id=str(conv.thread_id),
        status="completed",
        input_messages=[{"role": "system", "content": "[MetaAgent periodic report]"}],
        output_messages=[{"role": "assistant", "content": f"**MetaAgent Report:**\n\n{summary}"}],
        token_usage={},
    )
    session.add(row)
    await session.flush()


async def meta_worker_loop(stop: asyncio.Event) -> None:
    await asyncio.sleep(30)
    while not stop.is_set():
        await run_meta_tick_once()
        try:
            await asyncio.wait_for(asyncio.shield(stop.wait()), timeout=META_TICK_INTERVAL_SEC)
        except TimeoutError:
            pass
