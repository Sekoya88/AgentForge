from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.models import MetaProposalModel


class MetaProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        proposal_type: str,
        title: str,
        body: str,
        payload: dict,
        source: str,
        agent_id: uuid.UUID | None = None,
        skill_id: uuid.UUID | None = None,
    ) -> MetaProposalModel:
        row = MetaProposalModel(
            user_id=user_id,
            proposal_type=proposal_type,
            agent_id=agent_id,
            skill_id=skill_id,
            title=title,
            body=body,
            payload=payload,
            status="pending",
            source=source,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_pending(self, user_id: uuid.UUID) -> list[MetaProposalModel]:
        result = await self._session.execute(
            select(MetaProposalModel)
            .where(
                MetaProposalModel.user_id == user_id,
                MetaProposalModel.status == "pending",
            )
            .order_by(MetaProposalModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, proposal_id: uuid.UUID, user_id: uuid.UUID) -> MetaProposalModel | None:
        result = await self._session.execute(
            select(MetaProposalModel).where(
                MetaProposalModel.id == proposal_id,
                MetaProposalModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def set_status(self, proposal_id: uuid.UUID, status: str) -> MetaProposalModel:
        row = await self._session.get(MetaProposalModel, proposal_id)
        if row is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        row.status = status
        row.reviewed_at = datetime.now(UTC)
        await self._session.flush()
        return row

    async def count_pending(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).where(
                MetaProposalModel.user_id == user_id,
                MetaProposalModel.status == "pending",
            )
        )
        return result.scalar() or 0
