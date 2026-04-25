from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.entities.agent import Agent
from app.domain.entities.agent_schedule import AgentSchedule
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
        skills: list[str] | None = None,
        execution_policy: dict[str, Any] | None = None,
        collect_speech_examples: bool | None = None,
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
        skills: list[str] | None = None,
        execution_policy: dict[str, Any] | None = None,
        collect_speech_examples: bool | None = None,
    ) -> Agent | None:
        pass

    @abstractmethod
    async def delete(self, agent_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    async def get_latest_version_number(self, agent_id: UUID) -> int:
        """Max agent_versions.version_number for this agent, or 0 if none."""

    @abstractmethod
    async def create_execution(
        self,
        agent_id: UUID,
        user_id: UUID,
        thread_id: str,
        input_messages: list[MessageDict],
        agent_version_number: int | None = None,
        *,
        trigger_source: str = "api",
        schedule_id: UUID | None = None,
        compare_group_id: UUID | None = None,
        compare_label: str | None = None,
        model_config_override: dict[str, Any] | None = None,
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
    async def list_executions_for_thread(
        self,
        agent_id: UUID,
        user_id: UUID,
        thread_id: str,
    ) -> list[Execution]:
        """Completed executions for this agent + conversation thread, oldest first."""

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
        output_audio_b64: str | None = None,
        input_audio_b64: str | None = None,
        output_audio_url: str | None = None,
        input_audio_url: str | None = None,
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

    @abstractmethod
    async def delete_version(self, agent_id: UUID, user_id: UUID, version_number: int) -> bool:
        """Delete a version snapshot. Returns False if not found or is the current version."""
        pass

    @abstractmethod
    async def set_alias(
        self, agent_id: UUID, user_id: UUID, name: str, version_number: int
    ) -> None:
        """Create or update an alias pointing to a specific version number."""
        pass

    @abstractmethod
    async def get_alias(self, agent_id: UUID, user_id: UUID, name: str) -> int | None:
        """Resolve an alias name to a version number, return None if not found."""
        pass

    @abstractmethod
    async def list_aliases(self, agent_id: UUID, user_id: UUID) -> dict[str, int]:
        """Return all aliases for an agent as {name: version_number}."""
        pass

    @abstractmethod
    async def create_schedule(
        self,
        agent_id: UUID,
        user_id: UUID,
        cron_expression: str,
        input_payload: dict[str, Any],
        *,
        alias: str | None = None,
        enabled: bool = True,
        next_run_at: datetime,
    ) -> AgentSchedule:
        pass

    @abstractmethod
    async def get_schedule(
        self, agent_id: UUID, user_id: UUID, schedule_id: UUID
    ) -> AgentSchedule | None:
        pass

    @abstractmethod
    async def list_schedules(self, agent_id: UUID, user_id: UUID) -> list[AgentSchedule]:
        pass

    @abstractmethod
    async def update_schedule(
        self,
        agent_id: UUID,
        user_id: UUID,
        schedule_id: UUID,
        *,
        cron_expression: str | None = None,
        input_payload: dict[str, Any] | None = None,
        set_alias: bool = False,
        alias: str | None = None,
        enabled: bool | None = None,
    ) -> AgentSchedule | None:
        """When set_alias is True, set alias (None clears). Omit other fields to leave unchanged."""

    @abstractmethod
    async def delete_schedule(self, agent_id: UUID, user_id: UUID, schedule_id: UUID) -> bool:
        pass

    @abstractmethod
    async def list_due_schedules(self, before: datetime, *, limit: int = 50) -> list[AgentSchedule]:
        """Schedules with enabled=true and next_run_at <= before (worker only)."""

    @abstractmethod
    async def claim_due_schedules(
        self, before: datetime, *, limit: int = 50
    ) -> list[AgentSchedule]:
        """Lock due rows with SKIP LOCKED and advance next_run_at in the same transaction."""

    @abstractmethod
    async def update_schedule_run_times(
        self,
        schedule_id: UUID,
        *,
        last_run_at: datetime,
        next_run_at: datetime,
    ) -> None:
        pass
