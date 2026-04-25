from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.execution_policy import ExecutionPolicyValidated
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
    execution_policy: ExecutionPolicyValidated
    collect_speech_examples: bool
    status: str
    security_score: float | None
    health_score: float | None
    inbound_webhook_secret: str | None
    created_at: datetime
    updated_at: datetime
    budget_limit_usd: float | None = None
    budget_alert_threshold: float = 0.8
