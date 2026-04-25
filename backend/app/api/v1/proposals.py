from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_session
from app.domain.entities.user import User
from app.infrastructure.persistence.postgres.meta_proposal_repo import MetaProposalRepository

router = APIRouter(prefix="/proposals", tags=["proposals"])


class ProposalOut(BaseModel):
    id: str
    proposal_type: str
    title: str
    body: str
    status: str
    source: str
    created_at: str
    agent_id: str | None
    skill_id: str | None


def _to_out(row) -> ProposalOut:
    return ProposalOut(
        id=str(row.id),
        proposal_type=row.proposal_type,
        title=row.title,
        body=row.body,
        status=row.status,
        source=row.source,
        created_at=row.created_at.isoformat(),
        agent_id=str(row.agent_id) if row.agent_id else None,
        skill_id=str(row.skill_id) if row.skill_id else None,
    )


@router.get("", response_model=list[ProposalOut])
async def list_proposals(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProposalOut]:
    repo = MetaProposalRepository(session)
    rows = await repo.list_pending(user_id=user.id)
    return [_to_out(r) for r in rows]


@router.get("/count")
async def count_pending(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    repo = MetaProposalRepository(session)
    count = await repo.count_pending(user_id=user.id)
    return {"count": count}


@router.post("/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    from app.application.services.approval_service import ApprovalService
    from app.application.services.skill_service import SkillService
    from app.infrastructure.persistence.postgres.skill_repo import PostgresSkillRepository

    proposal_repo = MetaProposalRepository(session)
    skill_repo = PostgresSkillRepository(session)
    skill_svc = SkillService(repo=skill_repo)
    approval_svc = ApprovalService(
        proposal_repo=proposal_repo,
        skill_service=skill_svc,
        agent_service=None,
    )
    try:
        return await approval_svc.apply(proposal_id=proposal_id, user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    from app.application.services.approval_service import ApprovalService

    proposal_repo = MetaProposalRepository(session)
    approval_svc = ApprovalService(
        proposal_repo=proposal_repo, skill_service=None, agent_service=None
    )
    try:
        return await approval_svc.reject(proposal_id=proposal_id, user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
