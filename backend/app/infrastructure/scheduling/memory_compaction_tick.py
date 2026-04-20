"""Hourly tick: run per-user Forge memory compaction when due."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.application.services.forge_memory_service import ForgeMemoryService
from app.application.services.user_preferences_service import _next_weekday_at_hour
from app.infrastructure.persistence.postgres.forge_memory_repo import PostgresForgeMemoryRepository
from app.infrastructure.persistence.postgres.models import UserPreferencesModel
from app.infrastructure.persistence.postgres.session import session_scope

log = logging.getLogger(__name__)

MEMORY_TICK_INTERVAL_SEC = 3600  # 1 hour


async def run_memory_compaction_tick_once() -> None:
    now = datetime.now(UTC)
    async with session_scope() as session:
        result = await session.execute(
            select(UserPreferencesModel).where(
                UserPreferencesModel.memory_enabled.is_(True),
                UserPreferencesModel.memory_next_run_at <= now,
            )
        )
        due_prefs = list(result.scalars().all())

    # Collect only user_ids from the detached rows; re-fetch inside per-user session
    due_user_ids = [row.user_id for row in due_prefs]

    for user_id in due_user_ids:
        try:
            async with session_scope() as session:
                # Import here to avoid circular at module load
                from app.application.services.secrets_service import SecretsService
                from app.infrastructure.persistence.postgres.user_secrets_repo import (
                    PostgresUserSecretsRepository,
                )

                secrets_svc = SecretsService(PostgresUserSecretsRepository(session))
                secrets = await secrets_svc.get_decrypted_secrets(user_id)
                openai_key = secrets.get("openai_key")
                anthropic_key = secrets.get("anthropic_key")

                if not openai_key or not anthropic_key:
                    log.debug(
                        "memory_compaction_skipped_no_keys",
                        extra={"user_id": str(user_id)},
                    )
                    continue

                repo = PostgresForgeMemoryRepository(session)
                svc = ForgeMemoryService(repo, session)
                count = await svc.compact(user_id, openai_key, anthropic_key)

                # Re-fetch prefs inside this session to avoid detached-instance mutation
                prefs_row = await session.get(UserPreferencesModel, user_id)
                if prefs_row is not None:
                    prefs_row.memory_last_compacted_at = now
                    prefs_row.memory_next_run_at = _next_weekday_at_hour(
                        prefs_row.memory_compaction_day,
                        prefs_row.memory_compaction_hour,
                        now,
                    )

                log.info(
                    "forge_memory_compacted",
                    extra={"user_id": str(user_id), "new_chunks": count},
                )
        except Exception:
            log.exception("forge_memory_compaction_failed", extra={"user_id": str(user_id)})


async def memory_compaction_worker_loop(stop: asyncio.Event) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=10)
        return
    except TimeoutError:
        pass
    while not stop.is_set():
        try:
            await run_memory_compaction_tick_once()
        except Exception:
            log.exception("memory_compaction_tick_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=MEMORY_TICK_INTERVAL_SEC)
        except TimeoutError:
            continue
        return
