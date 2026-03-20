from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Campaign:
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
