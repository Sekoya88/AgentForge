from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.value_objects import MessageDict


@dataclass(frozen=True, slots=True)
class Execution:
    id: UUID
    agent_id: UUID
    user_id: UUID | None
    agent_version_number: int | None
    thread_id: str
    status: str
    input_messages: list[MessageDict]
    output_messages: list[MessageDict] | None
    interrupt_state: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None
    token_usage: dict[str, Any] | None
    duration_ms: int | None
    output_audio_b64: str | None = None
