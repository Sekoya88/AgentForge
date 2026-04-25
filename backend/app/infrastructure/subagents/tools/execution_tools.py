from __future__ import annotations

import uuid

from langchain_core.tools import tool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.execution_feedback_repo import (
    ExecutionFeedbackRepository,
)
from app.infrastructure.persistence.postgres.models import ExecutionFeedbackModel, ExecutionModel


def make_execution_tools(
    user_id: uuid.UUID,
    feedback_repo: ExecutionFeedbackRepository,
    session: AsyncSession,
) -> list:
    """Return execution analysis tools bound to this session."""

    @tool
    async def get_feedback_summary(agent_id: str | None = None) -> str:
        """Get aggregated feedback summary. Pass agent_id to filter to one agent."""
        query = select(
            ExecutionFeedbackModel.agent_id,
            func.avg(ExecutionFeedbackModel.score).label("avg_score"),
            func.count().label("total"),
        ).where(ExecutionFeedbackModel.user_id == user_id)

        if agent_id:
            query = query.where(ExecutionFeedbackModel.agent_id == uuid.UUID(agent_id))

        query = query.group_by(ExecutionFeedbackModel.agent_id)
        result = await session.execute(query)
        rows = result.all()

        if not rows:
            return "No feedback found."

        lines = [
            f"agent={row.agent_id} avg_score={row.avg_score:.2f} total={row.total}" for row in rows
        ]
        return "\n".join(lines)

    @tool
    async def search_failed_executions(agent_id: str | None = None, limit: int = 20) -> str:
        """Return recent failed executions. Pass agent_id to filter to one agent."""
        query = (
            select(ExecutionModel)
            .where(
                ExecutionModel.user_id == user_id,
                ExecutionModel.status == "failed",
            )
            .order_by(ExecutionModel.started_at.desc())
            .limit(limit)
        )
        if agent_id:
            query = query.where(ExecutionModel.agent_id == uuid.UUID(agent_id))

        result = await session.execute(query)
        rows = list(result.scalars().all())

        if not rows:
            return "No failed executions found."

        lines = []
        for ex in rows:
            out_msgs = ex.output_messages or []
            last_msg = out_msgs[-1].get("content", "")[:200] if out_msgs else "no output"
            lines.append(
                f"execution_id={ex.id} agent_id={ex.agent_id} "
                f"duration_ms={ex.duration_ms} last_output={last_msg!r}"
            )
        return "\n".join(lines)

    return [get_feedback_summary, search_failed_executions]
