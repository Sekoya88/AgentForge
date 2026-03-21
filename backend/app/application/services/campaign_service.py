import asyncio
import logging
from typing import Any
from uuid import UUID

from app.domain.entities.campaign import Campaign
from app.domain.exceptions import AgentNotFoundError, CampaignNotFoundError
from app.domain.ports.agent_repository import AgentRepository
from app.domain.ports.campaign_repository import CampaignRepository
from app.domain.ports.redteam_engine import RedTeamEngine
from app.domain.value_objects import CampaignConfig
from app.infrastructure.persistence.postgres.agent_repo import PostgresAgentRepository
from app.infrastructure.persistence.postgres.campaign_repo import PostgresCampaignRepository
from app.infrastructure.persistence.postgres.session import get_session_factory

log = logging.getLogger(__name__)


class CampaignService:
    def __init__(
        self,
        campaigns: CampaignRepository,
        agents: AgentRepository,
        redteam: RedTeamEngine,
    ) -> None:
        self._campaigns = campaigns
        self._agents = agents
        self._redteam = redteam

    def _build_config(
        self,
        agent_id: UUID,
        plugins: list[str],
        strategies: list[str],
    ) -> CampaignConfig:
        return CampaignConfig(
            model_config={
                "agent_id": str(agent_id),
                "plugins": plugins,
                "strategies": strategies,
            }
        )

    async def launch(
        self,
        user_id: UUID,
        agent_id: UUID,
        plugins: list[str],
        strategies: list[str],
        *,
        run_async: bool,
    ) -> Campaign:
        agent = await self._agents.get_by_id(agent_id, user_id)
        if agent is None:
            raise AgentNotFoundError(str(agent_id))
        config = self._build_config(agent_id, plugins, strategies)
        c = await self._campaigns.create(user_id, agent_id, config)

        if run_async:
            asyncio.create_task(
                self._run_background(c.id, agent_id, user_id, config, agent.name),
                name=f"campaign-{c.id}",
            )
            out = await self._campaigns.get_by_id(c.id, user_id)
            assert out is not None
            return out

        await self._campaigns.update_running(c.id)
        try:
            result = await self._redteam.run_assessment(config, agent.name)
            await self._campaigns.complete(
                c.id,
                overall_score=float(result["overall_score"]),
                total_tests=int(result["total_tests"]),
                passed_tests=int(result["passed_tests"]),
                failed_tests=int(result["failed_tests"]),
                report=dict(result["report"]),
                vulnerabilities=dict(result["vulnerabilities"]),
            )
            await self._agents.update_security_score(
                agent_id, user_id, float(result["overall_score"])
            )
        except Exception as e:
            log.exception("campaign_sync_failed", extra={"campaign_id": str(c.id)})
            await self._campaigns.fail(c.id, str(e))
        final = await self._campaigns.get_by_id(c.id, user_id)
        assert final is not None
        return final

    async def _run_background(
        self,
        campaign_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        config: CampaignConfig,
        agent_label: str,
    ) -> None:
        factory = get_session_factory()
        try:
            async with factory() as session:
                c_repo = PostgresCampaignRepository(session)
                await c_repo.update_running(campaign_id)
                await session.commit()

            result = await self._redteam.run_assessment(config, agent_label)

            async with factory() as session:
                c_repo = PostgresCampaignRepository(session)
                a_repo = PostgresAgentRepository(session)
                await c_repo.complete(
                    campaign_id,
                    overall_score=float(result["overall_score"]),
                    total_tests=int(result["total_tests"]),
                    passed_tests=int(result["passed_tests"]),
                    failed_tests=int(result["failed_tests"]),
                    report=dict(result["report"]),
                    vulnerabilities=dict(result["vulnerabilities"]),
                )
                await a_repo.update_security_score(
                    agent_id, user_id, float(result["overall_score"])
                )
                await session.commit()
        except Exception as e:
            log.exception("campaign_async_failed", extra={"campaign_id": str(campaign_id)})
            try:
                async with factory() as session:
                    c_repo = PostgresCampaignRepository(session)
                    await c_repo.fail(campaign_id, str(e))
                    await session.commit()
            except Exception:
                log.exception("campaign_fail_persist_failed")

    async def list_campaigns(self, user_id: UUID) -> list[Campaign]:
        return await self._campaigns.list_for_user(user_id)

    async def get(self, campaign_id: UUID, user_id: UUID) -> Campaign:
        c = await self._campaigns.get_by_id(campaign_id, user_id)
        if c is None:
            raise CampaignNotFoundError(str(campaign_id))
        return c

    async def report_payload(self, campaign_id: UUID, user_id: UUID) -> dict[str, Any]:
        c = await self.get(campaign_id, user_id)
        if c.report is None:
            return {"status": c.status, "message": "Report not available yet"}
        return c.report

    async def delete(self, campaign_id: UUID, user_id: UUID) -> None:
        ok = await self._campaigns.delete(campaign_id, user_id)
        if not ok:
            raise CampaignNotFoundError(str(campaign_id))
