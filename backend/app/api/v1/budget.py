"""Budget management endpoints for agents.

GET  /api/v1/agents/{agent_id}/budget  — current 30-day spend vs limit
PUT  /api/v1/agents/{agent_id}/budget  — set or clear budget limit
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_session
from app.domain.entities.user import User
from app.domain.services.budget_service import BudgetService
from app.infrastructure.persistence.postgres.models import AgentModel, ExecutionModel

router = APIRouter(prefix="/agents", tags=["budget"])

_budget_service = BudgetService()


class BudgetResponse(BaseModel):
    agent_id: UUID
    period_days: int
    spent_usd: float
    limit_usd: float | None
    alert_threshold: float
    status: str  # "ok" | "warning" | "exceeded"


class BudgetUpdateRequest(BaseModel):
    limit_usd: float | None = None
    alert_threshold: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("limit_usd")
    @classmethod
    def limit_must_be_positive(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("limit_usd must be >= 0")
        return v


async def _get_owned_agent(
    agent_id: UUID,
    session: AsyncSession,
    user: User,
) -> AgentModel:
    """Fetch an AgentModel and verify the current user owns it."""
    result = await session.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent_model = result.scalar_one_or_none()
    if agent_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if agent_model.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return agent_model


@router.get("/{agent_id}/budget", response_model=BudgetResponse)
async def get_agent_budget(
    agent_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> BudgetResponse:
    """Return the 30-day rolling spend and budget status for an agent."""
    agent_model = await _get_owned_agent(agent_id, session, user)

    since = datetime.now(UTC) - timedelta(days=30)
    result = await session.execute(
        select(ExecutionModel.token_usage).where(
            ExecutionModel.agent_id == agent_id,
            ExecutionModel.started_at >= since,
        )
    )
    rows = result.scalars().all()

    total_spent = sum(_budget_service.estimate_cost_usd(row) for row in rows)

    # Build a minimal duck-typed object so BudgetService.check_budget works
    class _AgentLike:
        budget_limit_usd = agent_model.budget_limit_usd
        budget_alert_threshold = agent_model.budget_alert_threshold or 0.8

    budget_status = _budget_service.check_budget(_AgentLike(), total_spent)

    return BudgetResponse(
        agent_id=agent_id,
        period_days=30,
        spent_usd=total_spent,
        limit_usd=agent_model.budget_limit_usd,
        alert_threshold=agent_model.budget_alert_threshold or 0.8,
        status=budget_status["status"],
    )


@router.put("/{agent_id}/budget", response_model=BudgetResponse)
async def set_agent_budget(
    agent_id: UUID,
    body: BudgetUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> BudgetResponse:
    """Set or clear the budget limit and alert threshold for an agent."""
    agent_model = await _get_owned_agent(agent_id, session, user)

    agent_model.budget_limit_usd = body.limit_usd
    agent_model.budget_alert_threshold = body.alert_threshold
    await session.flush()
    await session.refresh(agent_model)

    since = datetime.now(UTC) - timedelta(days=30)
    result = await session.execute(
        select(ExecutionModel.token_usage).where(
            ExecutionModel.agent_id == agent_id,
            ExecutionModel.started_at >= since,
        )
    )
    rows = result.scalars().all()
    total_spent = sum(_budget_service.estimate_cost_usd(row) for row in rows)

    class _AgentLike:
        budget_limit_usd = agent_model.budget_limit_usd
        budget_alert_threshold = agent_model.budget_alert_threshold or 0.8

    budget_status = _budget_service.check_budget(_AgentLike(), total_spent)

    return BudgetResponse(
        agent_id=agent_id,
        period_days=30,
        spent_usd=total_spent,
        limit_usd=agent_model.budget_limit_usd,
        alert_threshold=agent_model.budget_alert_threshold or 0.8,
        status=budget_status["status"],
    )
