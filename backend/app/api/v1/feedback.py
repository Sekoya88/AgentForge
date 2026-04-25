from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.application.services.feedback_service import FeedbackService
from app.dependencies import get_session
from app.domain.user import User
from app.infrastructure.persistence.postgres.execution_feedback_repo import (
    ExecutionFeedbackRepository,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class SubmitFeedbackRequest(BaseModel):
    execution_id: uuid.UUID
    agent_id: uuid.UUID
    score: float = Field(ge=0.0, le=1.0)
    comment: str | None = None
    category: str = Field(default="other", pattern="^(failure|quality|speed|suggestion|other)$")


class FeedbackResponse(BaseModel):
    id: str
    score: float
    category: str
    comment: str | None


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: SubmitFeedbackRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FeedbackResponse:
    repo = ExecutionFeedbackRepository(session)
    svc = FeedbackService(repo=repo)
    result = await svc.submit(
        execution_id=body.execution_id,
        agent_id=body.agent_id,
        user_id=user.id,
        score=body.score,
        comment=body.comment,
        category=body.category,
    )
    return FeedbackResponse(**result)


@router.get("/agents/{agent_id}/summary")
async def get_feedback_summary(
    agent_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    repo = ExecutionFeedbackRepository(session)
    svc = FeedbackService(repo=repo)
    return await svc.get_summary(agent_id=agent_id)
