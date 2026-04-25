from __future__ import annotations

import uuid
from typing import Any

from app.infrastructure.persistence.postgres.execution_feedback_repo import (
    ExecutionFeedbackRepository,
)


class FeedbackService:
    def __init__(self, repo: ExecutionFeedbackRepository) -> None:
        self._repo = repo

    async def submit(
        self,
        *,
        execution_id: uuid.UUID,
        agent_id: uuid.UUID,
        user_id: uuid.UUID | None,
        score: float,
        comment: str | None,
        category: str,
    ) -> dict[str, Any]:
        row = await self._repo.create(
            execution_id=execution_id,
            agent_id=agent_id,
            user_id=user_id,
            score=score,
            comment=comment,
            category=category,
        )
        return {
            "id": str(row.id),
            "score": row.score,
            "category": row.category,
            "comment": row.comment,
        }

    async def get_summary(self, agent_id: uuid.UUID) -> dict[str, Any]:
        rows = await self._repo.list_by_agent(agent_id)
        avg = await self._repo.avg_score_by_agent(agent_id)
        return {
            "agent_id": str(agent_id),
            "total": len(rows),
            "avg_score": round(avg, 3) if avg is not None else None,
            "recent": [
                {"score": r.score, "category": r.category, "comment": r.comment} for r in rows[:10]
            ],
        }
