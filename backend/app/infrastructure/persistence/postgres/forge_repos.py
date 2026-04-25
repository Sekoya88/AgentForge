"""Repositories for ForgeConversation and ForgeExecution."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.models import (
    ForgeConversationModel,
    ForgeExecutionModel,
)


class ForgeConversationRepo:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def create(
        self,
        user_id: UUID,
        provider: str,
        model: str,
        title: str | None = None,
    ) -> ForgeConversationModel:
        thread_id = str(uuid4())
        conv = ForgeConversationModel(
            id=uuid4(),
            user_id=user_id,
            thread_id=thread_id,
            title=title or "New conversation",
            provider=provider,
            model=model,
        )
        self._s.add(conv)
        await self._s.flush()
        return conv

    async def list_by_user(self, user_id: UUID) -> list[ForgeConversationModel]:
        result = await self._s.execute(
            select(ForgeConversationModel)
            .where(ForgeConversationModel.user_id == user_id)
            .order_by(ForgeConversationModel.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, conv_id: UUID, user_id: UUID) -> ForgeConversationModel | None:
        result = await self._s.execute(
            select(ForgeConversationModel).where(
                ForgeConversationModel.id == conv_id,
                ForgeConversationModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, conv_id: UUID, user_id: UUID) -> None:
        await self._s.execute(
            delete(ForgeConversationModel).where(
                ForgeConversationModel.id == conv_id,
                ForgeConversationModel.user_id == user_id,
            )
        )

    async def update_last_message(self, conv_id: UUID) -> None:
        await self._s.execute(
            update(ForgeConversationModel)
            .where(ForgeConversationModel.id == conv_id)
            .values(
                last_message_at=datetime.now(UTC),
                message_count=ForgeConversationModel.message_count + 1,
            )
        )


class ForgeExecutionRepo:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def create(
        self,
        user_id: UUID,
        conv_id: UUID,
        thread_id: str,
        input_messages: list[dict],
    ) -> ForgeExecutionModel:
        exe = ForgeExecutionModel(
            id=uuid4(),
            user_id=user_id,
            conversation_id=conv_id,
            thread_id=thread_id,
            status="running",
            input_messages=input_messages,
        )
        self._s.add(exe)
        await self._s.flush()
        return exe

    async def list_by_conversation(
        self, conv_id: UUID, limit: int = 24
    ) -> list[ForgeExecutionModel]:
        result = await self._s.execute(
            select(ForgeExecutionModel)
            .where(ForgeExecutionModel.conversation_id == conv_id)
            .order_by(ForgeExecutionModel.started_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def complete(
        self,
        exec_id: UUID,
        output_messages: list[dict],
        token_usage: dict,
    ) -> None:
        now = datetime.now(UTC)
        await self._s.execute(
            update(ForgeExecutionModel)
            .where(ForgeExecutionModel.id == exec_id)
            .values(
                status="completed",
                output_messages=output_messages,
                token_usage=token_usage,
                completed_at=now,
            )
        )

    async def fail(self, exec_id: UUID, error: str) -> None:
        await self._s.execute(
            update(ForgeExecutionModel)
            .where(ForgeExecutionModel.id == exec_id)
            .values(
                status="failed",
                output_messages=[{"role": "error", "content": error}],
                completed_at=datetime.now(UTC),
            )
        )
