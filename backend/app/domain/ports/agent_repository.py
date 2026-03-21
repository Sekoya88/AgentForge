from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.domain.entities.agent import Agent
from app.domain.entities.execution import Execution
from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.value_objects import AgentModelConfig, InterruptConfig, MessageDict


class AgentRepository(ABC):
    @abstractmethod
    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        graph_definition: GraphDefinitionValidated,
        model_config: AgentModelConfig,
    ) -> Agent:
        pass

    @abstractmethod
    async def get_by_id(self, agent_id: UUID, user_id: UUID) -> Agent | None:
        pass

    @abstractmethod
    async def list_for_user(self, user_id: UUID) -> list[Agent]:
        pass

    @abstractmethod
    async def update(
        self,
        agent_id: UUID,
        user_id: UUID,
        name: str | None,
        description: str | None,
        graph_definition: GraphDefinitionValidated | None,
        model_config: AgentModelConfig | None,
        status: str | None,
        interrupt_config: InterruptConfig | None = None,
    ) -> Agent | None:
        pass

    @abstractmethod
    async def delete(self, agent_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    async def create_execution(
        self,
        agent_id: UUID,
        user_id: UUID,
        thread_id: str,
        input_messages: list[MessageDict],
    ) -> Execution:
        pass

    @abstractmethod
    async def get_execution(
        self, agent_id: UUID, execution_id: UUID, user_id: UUID
    ) -> Execution | None:
        pass

    @abstractmethod
    async def list_executions(self, agent_id: UUID, user_id: UUID) -> list[Execution]:
        pass

    @abstractmethod
    async def update_execution(
        self,
        execution_id: UUID,
        status: str | None = None,
        output_messages: list[MessageDict] | None = None,
        token_usage: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        completed_at: bool = False,
        interrupt_state: dict[str, Any] | None = None,
        clear_interrupt_state: bool = False,
    ) -> None:
        pass

    @abstractmethod
    async def update_security_score(
        self,
        agent_id: UUID,
        user_id: UUID,
        security_score: float,
    ) -> None:
        pass
