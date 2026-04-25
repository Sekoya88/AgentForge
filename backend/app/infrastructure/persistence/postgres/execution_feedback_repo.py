from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.models import ExecutionFeedbackModel


class ExecutionFeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        execution_id: uuid.UUID,
        agent_id: uuid.UUID,
        user_id: uuid.UUID | None,
        score: float,
        comment: str | None,
        category: str,
    ) -> ExecutionFeedbackModel:
        row = ExecutionFeedbackModel(
            execution_id=execution_id,
            agent_id=agent_id,
            user_id=user_id,
            score=score,
            comment=comment,
            category=category,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_by_agent(
        self, agent_id: uuid.UUID, *, limit: int = 50
    ) -> list[ExecutionFeedbackModel]:
        result = await self._session.execute(
            select(ExecutionFeedbackModel)
            .where(ExecutionFeedbackModel.agent_id == agent_id)
            .order_by(ExecutionFeedbackModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_agent(self, agent_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).where(ExecutionFeedbackModel.agent_id == agent_id)
        )
        return result.scalar() or 0

    async def avg_score_by_agent(self, agent_id: uuid.UUID) -> float | None:
        result = await self._session.execute(
            select(func.avg(ExecutionFeedbackModel.score)).where(
                ExecutionFeedbackModel.agent_id == agent_id
            )
        )
        return result.scalar()
