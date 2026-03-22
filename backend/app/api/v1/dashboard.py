"""Dashboard aggregate stats + execution history."""

from typing import Annotated, Any

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
