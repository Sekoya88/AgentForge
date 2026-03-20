from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Agent:
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    graph_definition: dict[str, Any]
    model_config: dict[str, Any]
    interrupt_config: dict[str, Any]
    skills: list[str]
    status: str
    security_score: float | None
    created_at: datetime
    updated_at: datetime
