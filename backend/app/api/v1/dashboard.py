"""Dashboard aggregate stats + execution history."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_session
from app.domain.entities.user import User
from app.infrastructure.persistence.postgres.models import (
    AgentModel,
    CampaignModel,
    ExecutionModel,
    SkillModel,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard_stats(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    uid = user.id

    agents_q = await session.execute(select(func.count()).where(AgentModel.user_id == uid))
    agents_count = agents_q.scalar_one()

    execs_q = await session.execute(select(func.count()).where(ExecutionModel.user_id == uid))
    execs_count = execs_q.scalar_one()

    avg_dur_q = await session.execute(
        select(func.avg(ExecutionModel.duration_ms)).where(
            ExecutionModel.user_id == uid,
            ExecutionModel.duration_ms.isnot(None),
        )
    )
    avg_duration_ms = avg_dur_q.scalar_one()

    campaigns_q = await session.execute(
        select(func.count()).select_from(CampaignModel).where(CampaignModel.user_id == uid)
    )
    campaigns_count = campaigns_q.scalar_one()

    avg_score_q = await session.execute(
        select(func.avg(CampaignModel.overall_score)).where(
            CampaignModel.user_id == uid,
            CampaignModel.overall_score.isnot(None),
        )
    )
    avg_security_score = avg_score_q.scalar_one()

    # Calculate total estimated cost from token_usage jsonb
    total_cost_q = await session.execute(
        text(
            "SELECT COALESCE(SUM((token_usage->>'estimated_cost_usd')::numeric), 0) "
            "FROM executions WHERE user_id = :uid AND token_usage IS NOT NULL"
        ),
        {"uid": uid},
    )
    total_cost_usd = float(total_cost_q.scalar_one() or 0.0)

    skills_q = await session.execute(select(func.count()).where(SkillModel.user_id == uid))
    skills_count = skills_q.scalar_one()

    knowledge_q = await session.execute(
        text("SELECT count(DISTINCT source_title) FROM knowledge_chunks WHERE user_id = :uid"),
        {"uid": uid},
    )
    knowledge_sources = knowledge_q.scalar_one()

    recent_execs_q = await session.execute(
        select(
            ExecutionModel.id,
            ExecutionModel.agent_id,
            ExecutionModel.status,
            ExecutionModel.duration_ms,
            ExecutionModel.started_at,
        )
        .where(ExecutionModel.user_id == uid)
        .order_by(ExecutionModel.started_at.desc())
        .limit(10)
    )
    recent = [
        {
            "id": str(r.id),
            "agent_id": str(r.agent_id),
            "status": r.status,
            "duration_ms": r.duration_ms,
            "started_at": r.started_at.isoformat() if r.started_at else None,
        }
        for r in recent_execs_q.all()
    ]

    return {
        "agents": agents_count,
        "executions": execs_count,
        "avg_duration_ms": (round(avg_duration_ms, 1) if avg_duration_ms else None),
        "campaigns": campaigns_count,
        "avg_security_score": (round(avg_security_score, 2) if avg_security_score else None),
        "total_cost_usd": round(total_cost_usd, 4),
        "skills": skills_count,
        "knowledge_sources": knowledge_sources,
        "recent_executions": recent,
    }


@router.get("/executions")
async def all_executions(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    uid = user.id

    total_q = await session.execute(select(func.count()).where(ExecutionModel.user_id == uid))
    total = total_q.scalar_one()

    rows_q = await session.execute(
        select(
            ExecutionModel.id,
            ExecutionModel.agent_id,
            ExecutionModel.status,
            ExecutionModel.duration_ms,
            ExecutionModel.started_at,
            ExecutionModel.completed_at,
            ExecutionModel.token_usage,
            AgentModel.name.label("agent_name"),
        )
        .join(AgentModel, AgentModel.id == ExecutionModel.agent_id)
        .where(ExecutionModel.user_id == uid)
        .order_by(ExecutionModel.started_at.desc())
        .limit(limit)
        .offset(offset)
    )

    items = [
        {
            "id": str(r.id),
            "agent_id": str(r.agent_id),
            "agent_name": r.agent_name,
            "status": r.status,
            "duration_ms": r.duration_ms,
            "started_at": (r.started_at.isoformat() if r.started_at else None),
            "completed_at": (r.completed_at.isoformat() if r.completed_at else None),
            "token_usage": r.token_usage,
        }
        for r in rows_q.all()
    ]

    return {"total": total, "items": items}


@router.get("/metrics")
async def metrics(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    agent_id: Annotated[str | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> dict[str, Any]:
    uid = user.id

    agent_filter = "AND agent_id = CAST(:agent_id_val AS uuid)" if agent_id else ""
    sql = text(f"""
        SELECT
            date_trunc('day', started_at) AS day,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed,
            ROUND(AVG(duration_ms)::numeric, 0) AS avg_latency_ms,
            COALESCE(SUM((token_usage->>'total_tokens')::int), 0) AS total_tokens
        FROM executions
        WHERE user_id = :uid
          AND started_at >= NOW() - INTERVAL '{days} days'
          {agent_filter}
        GROUP BY date_trunc('day', started_at)
        ORDER BY day
    """)

    params: dict[str, Any] = {"uid": uid}
    if agent_id:
        params["agent_id_val"] = agent_id
    result = await session.execute(sql, params)
    rows = result.all()

    daily_stats = [
        {
            "day": str(r.day.date()) if r.day else None,
            "total": int(r.total),
            "completed": int(r.completed),
            "failed": int(r.failed),
            "avg_latency_ms": int(r.avg_latency_ms) if r.avg_latency_ms else 0,
            "total_tokens": int(r.total_tokens),
        }
        for r in rows
    ]

    total_executions = sum(d["total"] for d in daily_stats)
    total_failed = sum(d["failed"] for d in daily_stats)
    total_tokens = sum(d["total_tokens"] for d in daily_stats)
    latencies = [d["avg_latency_ms"] for d in daily_stats if d["avg_latency_ms"]]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0
    error_rate = round(total_failed / total_executions, 4) if total_executions else 0.0

    # Cost estimate: $0.01 per 1000 tokens as a rough default
    estimated_cost_usd = round(total_tokens * 0.00001, 4)

    return {
        "daily_stats": daily_stats,
        "summary": {
            "total_executions": total_executions,
            "error_rate": error_rate,
            "avg_latency_ms": avg_latency,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        },
    }


@router.get("/agents/{agent_id}/node-perf")
async def node_perf(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> dict[str, Any]:
    uid = user.id

    rows = await session.execute(
        select(
            ExecutionModel.id,
            ExecutionModel.status,
            ExecutionModel.duration_ms,
            ExecutionModel.started_at,
        )
        .where(ExecutionModel.user_id == uid, ExecutionModel.agent_id == agent_id)
        .order_by(ExecutionModel.started_at.desc())
        .limit(limit)
    )

    return {
        "executions": [
            {
                "id": str(r.id),
                "status": r.status,
                "duration_ms": r.duration_ms,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in rows.all()
        ]
    }
