from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.campaign import Campaign
from app.domain.ports.campaign_repository import CampaignRepository
from app.domain.value_objects import CampaignConfig
from app.infrastructure.persistence.postgres.models import CampaignModel


class PostgresCampaignRepository(CampaignRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: UUID,
        agent_id: UUID,
        config: CampaignConfig,
    ) -> Campaign:
        m = CampaignModel(
            user_id=user_id, agent_id=agent_id, config=config.to_dict(), status="pending"
        )
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)

    async def get_by_id(self, campaign_id: UUID, user_id: UUID) -> Campaign | None:
        m = await self._session.get(CampaignModel, campaign_id)
        if m is None or m.user_id != user_id:
            return None
        return self._to_entity(m)

    async def list_for_user(self, user_id: UUID) -> list[Campaign]:
        q = await self._session.execute(
            select(CampaignModel)
            .where(CampaignModel.user_id == user_id)
            .order_by(CampaignModel.created_at.desc())
        )
        return [self._to_entity(r) for r in q.scalars().all()]

    async def delete(self, campaign_id: UUID, user_id: UUID) -> bool:
        m = await self._session.get(CampaignModel, campaign_id)
        if m is None or m.user_id != user_id:
            return False
        await self._session.delete(m)
        return True

    async def update_running(self, campaign_id: UUID) -> None:
        m = await self._session.get(CampaignModel, campaign_id)
        if m is None:
            return
        m.status = "running"
        m.started_at = datetime.now(UTC)
        await self._session.flush()

    async def complete(
        self,
        campaign_id: UUID,
        *,
        overall_score: float,
        total_tests: int,
        passed_tests: int,
        failed_tests: int,
        report: dict[str, Any],
        vulnerabilities: dict[str, Any],
    ) -> None:
        m = await self._session.get(CampaignModel, campaign_id)
        if m is None:
            return
        m.status = "completed"
        m.overall_score = overall_score
        m.total_tests = total_tests
        m.passed_tests = passed_tests
        m.failed_tests = failed_tests
        m.report = report
        m.vulnerabilities = vulnerabilities
        m.completed_at = datetime.now(UTC)
        await self._session.flush()

    async def fail(self, campaign_id: UUID, error_message: str) -> None:
        m = await self._session.get(CampaignModel, campaign_id)
        if m is None:
            return
        m.status = "failed"
        m.report = {"error": error_message}
        m.completed_at = datetime.now(UTC)
        await self._session.flush()

    @staticmethod
    def _to_entity(m: CampaignModel) -> Campaign:
        return Campaign(
            id=m.id,
            agent_id=m.agent_id,
            user_id=m.user_id,
            config=CampaignConfig.model_validate(m.config),
            status=m.status or "pending",
            overall_score=m.overall_score,
            total_tests=m.total_tests,
            passed_tests=m.passed_tests,
            failed_tests=m.failed_tests,
            report=dict(m.report) if m.report else None,
            vulnerabilities=dict(m.vulnerabilities) if m.vulnerabilities else None,
            started_at=m.started_at,
            completed_at=m.completed_at,
            created_at=m.created_at,
        )
