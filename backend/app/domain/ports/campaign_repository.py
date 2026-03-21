from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.domain.entities.campaign import Campaign
from app.domain.value_objects import CampaignConfig


class CampaignRepository(ABC):
    @abstractmethod
    async def create(
        self,
        user_id: UUID,
        agent_id: UUID,
        config: CampaignConfig,
    ) -> Campaign:
        pass

    @abstractmethod
    async def get_by_id(self, campaign_id: UUID, user_id: UUID) -> Campaign | None:
        pass

    @abstractmethod
    async def list_for_user(self, user_id: UUID) -> list[Campaign]:
        pass

    @abstractmethod
    async def delete(self, campaign_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    async def update_running(self, campaign_id: UUID) -> None:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def fail(self, campaign_id: UUID, error_message: str) -> None:
        pass
