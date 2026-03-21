from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.value_objects import AgentModelConfig, InterruptConfig


@dataclass(frozen=True, slots=True)
class Agent:
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    graph_definition: GraphDefinitionValidated
    model_config: AgentModelConfig
    interrupt_config: InterruptConfig
    skills: list[str]
    status: str
    security_score: float | None
    created_at: datetime
    updated_at: datetime
