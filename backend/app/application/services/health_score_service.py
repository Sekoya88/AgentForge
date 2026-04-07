"""Compute composite agent health score (0-100)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.models import AgentModel, CampaignModel, ExecutionModel

log = logging.getLogger(__name__)

WEIGHTS = {
    "security": 0.30,  # from campaigns.overall_score
    "error_rate": 0.25,  # 1 - (failed/total) in last 7d
    "latency": 0.20,  # normalized latency (lower is better)
    "coverage": 0.15,  # has test executions? (binary: 0 or 1)
    "has_description": 0.10,  # agent has a description set
}


async def compute_health_score(agent_id: UUID, user_id: UUID, session: AsyncSession) -> float:
    """Compute and return health score 0-100 for an agent."""
    scores: dict[str, float] = {}

    # Security score (from latest campaign)
    camp_q = await session.execute(
        select(CampaignModel.overall_score)
        .where(CampaignModel.agent_id == agent_id, CampaignModel.overall_score.isnot(None))
        .order_by(CampaignModel.created_at.desc())
        .limit(1)
    )
    camp_score = camp_q.scalar_one_or_none()
    scores["security"] = (
        float(camp_score) if camp_score is not None else 50.0
    )  # neutral if no campaign

    # Error rate (last 7 days)
    exec_q = await session.execute(
        text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM executions
            WHERE agent_id = :agent_id
              AND started_at >= NOW() - INTERVAL '7 days'
        """),
        {"agent_id": agent_id},
    )
    row = exec_q.one()
    total, failed = row.total, row.failed
    if total > 0:
        error_rate = failed / total
        scores["error_rate"] = (1 - error_rate) * 100  # higher is better
    else:
        scores["error_rate"] = 50.0  # neutral if no executions

    # Latency (avg ms, normalize: 0ms=100, >=5000ms=0)
    lat_q = await session.execute(
        select(func.avg(ExecutionModel.duration_ms)).where(
            ExecutionModel.agent_id == agent_id,
            ExecutionModel.duration_ms.isnot(None),
            ExecutionModel.status == "completed",
        )
    )
    avg_ms = lat_q.scalar_one_or_none()
    if avg_ms is not None:
        # Linear: 0ms -> 100, 5000ms -> 0, clamp
        scores["latency"] = max(0.0, min(100.0, (1 - float(avg_ms) / 5000) * 100))
    else:
        scores["latency"] = 50.0  # neutral

    # Coverage: has at least 5 executions?
    if total >= 5:
        scores["coverage"] = 100.0
    elif total >= 1:
        scores["coverage"] = 60.0
    else:
        scores["coverage"] = 0.0

    # Has description?
    agent = await session.get(AgentModel, agent_id)
    scores["has_description"] = (
        100.0 if (agent and agent.description and len(agent.description) > 10) else 0.0
    )

    # Weighted sum
    final = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return round(final, 1)


async def refresh_agent_health_score(agent_id: UUID, user_id: UUID, session: AsyncSession) -> float:
    """Compute and persist the health score to AgentModel."""
    score = await compute_health_score(agent_id, user_id, session)
    agent = await session.get(AgentModel, agent_id)
    if agent:
        agent.health_score = score
        await session.commit()
    return score
