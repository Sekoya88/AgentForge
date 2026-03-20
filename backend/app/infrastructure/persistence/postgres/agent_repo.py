from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.agent import Agent
from app.domain.entities.execution import Execution
from app.domain.ports.agent_repository import AgentRepository
from app.infrastructure.persistence.postgres.models import AgentModel, ExecutionModel


class PostgresAgentRepository(AgentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        graph_definition: dict[str, Any],
        model_config: dict[str, Any],
    ) -> Agent:
        m = AgentModel(
            user_id=user_id,
            name=name,
            description=description,
            graph_definition=graph_definition,
            model_config=model_config,
        )
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._agent_to_entity(m)

    async def get_by_id(self, agent_id: UUID, user_id: UUID) -> Agent | None:
        q = await self._session.execute(
            select(AgentModel).where(AgentModel.id == agent_id, AgentModel.user_id == user_id)
        )
        row = q.scalar_one_or_none()
        return self._agent_to_entity(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[Agent]:
        q = await self._session.execute(
            select(AgentModel).where(AgentModel.user_id == user_id).order_by(AgentModel.created_at)
        )
        return [self._agent_to_entity(r) for r in q.scalars().all()]

    async def update(
        self,
        agent_id: UUID,
        user_id: UUID,
        name: str | None,
        description: str | None,
        graph_definition: dict[str, Any] | None,
        model_config: dict[str, Any] | None,
        status: str | None,
        interrupt_config: dict[str, Any] | None = None,
    ) -> Agent | None:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return None
        if name is not None:
            m.name = name
        if description is not None:
            m.description = description
        if graph_definition is not None:
            m.graph_definition = graph_definition
        if model_config is not None:
            m.model_config = model_config
        if status is not None:
            m.status = status
        if interrupt_config is not None:
            m.interrupt_config = interrupt_config
        await self._session.flush()
        await self._session.refresh(m)
        return self._agent_to_entity(m)

    async def delete(self, agent_id: UUID, user_id: UUID) -> bool:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return False
        await self._session.delete(m)
        return True

    async def create_execution(
        self,
        agent_id: UUID,
        user_id: UUID,
        thread_id: str,
        input_messages: list[dict[str, Any]],
    ) -> Execution:
        e = ExecutionModel(
            agent_id=agent_id,
            user_id=user_id,
            thread_id=thread_id,
            input_messages=input_messages,
            status="running",
        )
        self._session.add(e)
        await self._session.flush()
        await self._session.refresh(e)
        return self._exec_to_entity(e)

    async def get_execution(
        self, agent_id: UUID, execution_id: UUID, user_id: UUID
    ) -> Execution | None:
        e = await self._session.get(ExecutionModel, execution_id)
        if e is None or e.agent_id != agent_id or e.user_id != user_id:
            return None
        return self._exec_to_entity(e)

    async def list_executions(self, agent_id: UUID, user_id: UUID) -> list[Execution]:
        q = await self._session.execute(
            select(ExecutionModel)
            .where(
                ExecutionModel.agent_id == agent_id,
                ExecutionModel.user_id == user_id,
            )
            .order_by(ExecutionModel.started_at.desc())
        )
        return [self._exec_to_entity(r) for r in q.scalars().all()]

    async def update_execution(
        self,
        execution_id: UUID,
        status: str | None = None,
        output_messages: list[dict[str, Any]] | None = None,
        token_usage: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        completed_at: bool = False,
        interrupt_state: dict[str, Any] | None = None,
        clear_interrupt_state: bool = False,
    ) -> None:
        e = await self._session.get(ExecutionModel, execution_id)
        if e is None:
            return
        if status is not None:
            e.status = status
        if output_messages is not None:
            e.output_messages = output_messages
        if token_usage is not None:
            e.token_usage = token_usage
        if duration_ms is not None:
            e.duration_ms = duration_ms
        if clear_interrupt_state:
            e.interrupt_state = None
        elif interrupt_state is not None:
            e.interrupt_state = interrupt_state
        if completed_at:
            e.completed_at = datetime.now(UTC)
        await self._session.flush()

    async def update_security_score(
        self,
        agent_id: UUID,
        user_id: UUID,
        security_score: float,
    ) -> None:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return
        m.security_score = security_score
        await self._session.flush()

    @staticmethod
    def _agent_to_entity(m: AgentModel) -> Agent:
        skills = list(m.skills) if m.skills is not None else []
        return Agent(
            id=m.id,
            user_id=m.user_id,
            name=m.name,
            description=m.description,
            graph_definition=dict(m.graph_definition),
            model_config=dict(m.model_config),
            interrupt_config=dict(m.interrupt_config or {}),
            skills=skills,
            status=m.status or "draft",
            security_score=m.security_score,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def _exec_to_entity(e: ExecutionModel) -> Execution:
        return Execution(
            id=e.id,
            agent_id=e.agent_id,
            user_id=e.user_id,
            thread_id=e.thread_id,
            status=e.status or "running",
            input_messages=list(e.input_messages),
            output_messages=list(e.output_messages) if e.output_messages else None,
            interrupt_state=dict(e.interrupt_state) if e.interrupt_state else None,
            started_at=e.started_at,
            completed_at=e.completed_at,
            token_usage=dict(e.token_usage) if e.token_usage else None,
            duration_ms=e.duration_ms,
        )
