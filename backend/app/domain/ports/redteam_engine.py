from abc import ABC, abstractmethod
from typing import Any


class RedTeamEngine(ABC):
    @abstractmethod
    async def run_assessment(
        self,
        config: dict[str, Any],
        agent_label: str,
    ) -> dict[str, Any]:
        """Result dict: scores, counts, report, vulnerabilities."""
