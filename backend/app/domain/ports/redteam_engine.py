from abc import ABC, abstractmethod
from typing import Any

from app.domain.value_objects import CampaignConfig


class RedTeamEngine(ABC):
    @abstractmethod
    async def run_assessment(
        self,
        config: CampaignConfig,
        agent_label: str,
    ) -> dict[str, Any]:
        """Result dict: scores, counts, report, vulnerabilities."""
