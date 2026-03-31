from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AgentSchedule:
    id: UUID
    agent_id: UUID
    user_id: UUID | None
    alias: str | None
    cron_expression: str
    input: dict[str, Any]
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime
    created_at: datetime
