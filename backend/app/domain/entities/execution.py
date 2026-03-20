from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Execution:
    id: UUID
    agent_id: UUID
    user_id: UUID | None
    thread_id: str
    status: str
    input_messages: list[dict[str, Any]]
    output_messages: list[dict[str, Any]] | None
    interrupt_state: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None
    token_usage: dict[str, Any] | None
    duration_ms: int | None
