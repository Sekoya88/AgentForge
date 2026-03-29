from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class FinetuneExample:
    id: UUID
    agent_id: UUID
    user_id: UUID | None
    execution_id: UUID | None
    input_messages: list[dict[str, Any]]
    output_messages: list[dict[str, Any]]
    score: float
    created_at: datetime
