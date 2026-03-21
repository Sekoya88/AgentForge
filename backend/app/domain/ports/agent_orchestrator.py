from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.orchestration_result import OrchestrationResult
from app.domain.ports.execution_events import ExecutionEventEmitter
from app.domain.value_objects import AgentModelConfig, MessageDict


class AgentOrchestrator(ABC):
    @abstractmethod
    async def run(
        self,
        agent_id: UUID,
        graph_definition: GraphDefinitionValidated,
        model_config: AgentModelConfig,
        input_messages: list[MessageDict],
        *,
        emitter: ExecutionEventEmitter | None = None,
        agent_label: str | None = None,
        execution_id: UUID | None = None,
    ) -> OrchestrationResult:
        pass

    @abstractmethod
    async def resume(
        self,
        execution_id: UUID,
        agent_id: UUID,
        graph_definition: GraphDefinitionValidated,
        model_config: AgentModelConfig,
        resume_value: Any,
        *,
        emitter: ExecutionEventEmitter | None = None,
        agent_label: str | None = None,
    ) -> OrchestrationResult:
        pass
