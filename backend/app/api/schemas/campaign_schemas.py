from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.campaign import Campaign


class LaunchCampaignRequest(BaseModel):
    agent_id: UUID
    plugins: list[str] = Field(default_factory=list)
    strategies: list[str] = Field(default_factory=list)
    run_async: bool = False


class CampaignResponse(BaseModel):
    id: UUID
    agent_id: UUID
    user_id: UUID | None
    config: dict[str, Any]
    status: str
    overall_score: float | None
    total_tests: int | None
    passed_tests: int | None
    failed_tests: int | None
    report: dict[str, Any] | None
    vulnerabilities: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, c: Campaign) -> "CampaignResponse":
        return cls(
            id=c.id,
            agent_id=c.agent_id,
            user_id=c.user_id,
            config=c.config,
            status=c.status,
            overall_score=c.overall_score,
            total_tests=c.total_tests,
            passed_tests=c.passed_tests,
            failed_tests=c.failed_tests,
            report=c.report,
            vulnerabilities=c.vulnerabilities,
            started_at=c.started_at,
            completed_at=c.completed_at,
            created_at=c.created_at,
        )
