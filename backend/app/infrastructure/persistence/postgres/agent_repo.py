import secrets as _secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.agent import Agent
from app.domain.entities.agent_schedule import AgentSchedule
from app.domain.entities.execution import Execution
from app.domain.execution_policy import parse_execution_policy
from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.ports.agent_repository import AgentRepository
from app.domain.schedule_cron import next_fire_after
from app.domain.value_objects import AgentModelConfig, InterruptConfig, MessageDict
from app.infrastructure.persistence.postgres.models import (
    AgentModel,
    AgentScheduleModel,
    AgentVersionModel,
    ExecutionModel,
)


@dataclass(frozen=True)
class AgentVersion:
    id: UUID
    agent_id: UUID
    version_number: int
    graph_definition: dict
    model_config: dict
    skills: list[str]
    execution_policy: dict[str, Any]
    change_note: str | None
    created_at: datetime


class PostgresAgentRepository(AgentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        pol = execution_policy if execution_policy is not None else {}
        m = AgentModel(
            user_id=user_id,
            name=name,
            description=description,
            graph_definition=graph_definition.to_dict(),
            model_config=model_config.to_dict(),
            interrupt_config={},
            skills=skills if skills is not None else [],
            execution_policy=pol,
        )
        if collect_speech_examples is not None:
            m.collect_speech_examples = collect_speech_examples
        m.inbound_webhook_secret = _secrets.token_urlsafe(32)
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
        graph_definition: GraphDefinitionValidated | None,
        model_config: AgentModelConfig | None,
        status: str | None,
        interrupt_config: InterruptConfig | None = None,
        skills: list[str] | None = None,
        execution_policy: dict[str, Any] | None = None,
        collect_speech_examples: bool | None = None,
    ) -> Agent | None:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return None
        if name is not None:
            m.name = name
        if description is not None:
            m.description = description
        if graph_definition is not None:
            m.graph_definition = graph_definition.to_dict()
        if model_config is not None:
            m.model_config = model_config.to_dict()
        if status is not None:
            m.status = status
        if interrupt_config is not None:
            m.interrupt_config = interrupt_config.to_dict()
        if skills is not None:
            m.skills = skills
        if execution_policy is not None:
            m.execution_policy = execution_policy
        if collect_speech_examples is not None:
            m.collect_speech_examples = collect_speech_examples
        await self._snapshot_version(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._agent_to_entity(m)

    async def delete(self, agent_id: UUID, user_id: UUID) -> bool:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return False
        await self._session.delete(m)
        return True

    async def get_latest_version_number(self, agent_id: UUID) -> int:
        res = await self._session.execute(
            select(func.coalesce(func.max(AgentVersionModel.version_number), 0)).where(
                AgentVersionModel.agent_id == agent_id
            )
        )
        return int(res.scalar_one())

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
        e = ExecutionModel(
            agent_id=agent_id,
            user_id=user_id,
            thread_id=thread_id,
            input_messages=[m.to_dict() for m in input_messages],
            status="running",
            agent_version_number=agent_version_number,
            trigger_source=trigger_source,
            schedule_id=schedule_id,
            compare_group_id=compare_group_id,
            compare_label=compare_label,
            model_config_override=model_config_override,
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

    async def list_executions_for_thread(
        self,
        agent_id: UUID,
        user_id: UUID,
        thread_id: str,
    ) -> list[Execution]:
        q = await self._session.execute(
            select(ExecutionModel)
            .where(
                ExecutionModel.agent_id == agent_id,
                ExecutionModel.user_id == user_id,
                ExecutionModel.thread_id == thread_id,
                ExecutionModel.status == "completed",
            )
            .order_by(ExecutionModel.started_at.asc())
        )
        return [self._exec_to_entity(r) for r in q.scalars().all()]

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
    ) -> None:
        e = await self._session.get(ExecutionModel, execution_id)
        if e is None:
            return
        if status is not None:
            e.status = status
        if output_messages is not None:
            e.output_messages = [m.to_dict() for m in output_messages]
        if token_usage is not None:
            e.token_usage = token_usage
        if duration_ms is not None:
            e.duration_ms = duration_ms
        if clear_interrupt_state:
            e.interrupt_state = None
        elif interrupt_state is not None:
            e.interrupt_state = interrupt_state
        if output_audio_b64 is not None:
            e.output_audio_b64 = output_audio_b64
        if input_audio_b64 is not None:
            e.input_audio_b64 = input_audio_b64
        if completed_at:
            e.completed_at = datetime.now(UTC)
        await self._session.flush()

    async def _snapshot_version(self, m: AgentModel, change_note: str | None = None) -> None:
        """Append a version snapshot for the current agent state."""
        res = await self._session.execute(
            select(func.coalesce(func.max(AgentVersionModel.version_number), 0)).where(
                AgentVersionModel.agent_id == m.id
            )
        )
        latest: int = res.scalar_one()
        v = AgentVersionModel(
            agent_id=m.id,
            version_number=latest + 1,
            graph_definition=dict(m.graph_definition),
            model_config=dict(m.model_config),
            skills=list(m.skills) if m.skills else [],
            execution_policy=dict(m.execution_policy or {}),
            change_note=change_note,
        )
        self._session.add(v)

    async def list_versions(self, agent_id: UUID, user_id: UUID) -> list[AgentVersion]:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return []
        q = await self._session.execute(
            select(AgentVersionModel)
            .where(AgentVersionModel.agent_id == agent_id)
            .order_by(AgentVersionModel.version_number.desc())
        )
        return [self._version_to_entity(v) for v in q.scalars().all()]

    async def get_version(
        self, agent_id: UUID, user_id: UUID, version_number: int
    ) -> AgentVersion | None:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return None
        q = await self._session.execute(
            select(AgentVersionModel).where(
                AgentVersionModel.agent_id == agent_id,
                AgentVersionModel.version_number == version_number,
            )
        )
        v = q.scalar_one_or_none()
        return self._version_to_entity(v) if v else None

    async def rollback_to_version(
        self, agent_id: UUID, user_id: UUID, version_number: int
    ) -> Agent | None:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return None
        q = await self._session.execute(
            select(AgentVersionModel).where(
                AgentVersionModel.agent_id == agent_id,
                AgentVersionModel.version_number == version_number,
            )
        )
        v = q.scalar_one_or_none()
        if v is None:
            return None
        m.graph_definition = dict(v.graph_definition)
        m.model_config = dict(v.model_config)
        m.skills = list(v.skills)
        m.execution_policy = dict(v.execution_policy or {})
        await self._snapshot_version(m, change_note=f"rollback to v{version_number}")
        await self._session.flush()
        await self._session.refresh(m)
        return self._agent_to_entity(m)

    async def delete_version(self, agent_id: UUID, user_id: UUID, version_number: int) -> bool:
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            return False
        # Refuse to delete the current (latest) version
        q = await self._session.execute(
            select(AgentVersionModel)
            .where(AgentVersionModel.agent_id == agent_id)
            .order_by(AgentVersionModel.version_number.desc())
            .limit(1)
        )
        latest = q.scalar_one_or_none()
        if latest and latest.version_number == version_number:
            return False
        result = await self._session.execute(
            select(AgentVersionModel).where(
                AgentVersionModel.agent_id == agent_id,
                AgentVersionModel.version_number == version_number,
            )
        )
        v = result.scalar_one_or_none()
        if v is None:
            return False
        await self._session.delete(v)
        await self._session.flush()
        return True

    async def execution_stats_by_version(
        self,
        agent_id: UUID,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        q = (
            select(
                ExecutionModel.agent_version_number,
                func.count().label("total"),
                func.sum(case((ExecutionModel.status == "completed", 1), else_=0)).label(
                    "completed"
                ),
                func.sum(case((ExecutionModel.status == "failed", 1), else_=0)).label("failed"),
                func.avg(ExecutionModel.duration_ms).label("avg_duration_ms"),
            )
            .where(
                ExecutionModel.agent_id == agent_id,
                ExecutionModel.user_id == user_id,
            )
            .group_by(ExecutionModel.agent_version_number)
            .order_by(ExecutionModel.agent_version_number)
        )
        res = await self._session.execute(q)
        out: list[dict[str, Any]] = []
        for row in res:
            out.append(
                {
                    "agent_version_number": row.agent_version_number,
                    "total": int(row.total),
                    "completed": int(row.completed or 0),
                    "failed": int(row.failed or 0),
                    "avg_duration_ms": float(row.avg_duration_ms)
                    if row.avg_duration_ms is not None
                    else None,
                }
            )
        return out

    @staticmethod
    def _version_to_entity(v: AgentVersionModel) -> AgentVersion:
        return AgentVersion(
            id=v.id,
            agent_id=v.agent_id,
            version_number=v.version_number,
            graph_definition=dict(v.graph_definition),
            model_config=dict(v.model_config),
            skills=list(v.skills) if v.skills else [],
            execution_policy=dict(v.execution_policy or {}),
            change_note=v.change_note,
            created_at=v.created_at,
        )

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
            graph_definition=GraphDefinitionValidated.model_validate(m.graph_definition),
            model_config=AgentModelConfig.model_validate(m.model_config),
            interrupt_config=InterruptConfig.model_validate(m.interrupt_config or {}),
            skills=skills,
            execution_policy=parse_execution_policy(m.execution_policy),
            collect_speech_examples=bool(m.collect_speech_examples),
            status=m.status or "draft",
            security_score=m.security_score,
            inbound_webhook_secret=m.inbound_webhook_secret,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def _exec_to_entity(e: ExecutionModel) -> Execution:
        return Execution(
            id=e.id,
            agent_id=e.agent_id,
            user_id=e.user_id,
            agent_version_number=e.agent_version_number,
            thread_id=e.thread_id,
            status=e.status or "running",
            input_messages=[MessageDict.model_validate(msg) for msg in e.input_messages],
            output_messages=[MessageDict.model_validate(msg) for msg in e.output_messages]
            if e.output_messages
            else None,
            interrupt_state=dict(e.interrupt_state) if e.interrupt_state else None,
            started_at=e.started_at,
            completed_at=e.completed_at,
            token_usage=dict(e.token_usage) if e.token_usage else None,
            duration_ms=e.duration_ms,
            input_audio_b64=e.input_audio_b64,
            output_audio_b64=e.output_audio_b64,
            trigger_source=e.trigger_source or "api",
            schedule_id=e.schedule_id,
            compare_group_id=e.compare_group_id,
            compare_label=e.compare_label,
            model_config_override=dict(e.model_config_override)
            if e.model_config_override is not None
            else None,
        )

    @staticmethod
    def _schedule_to_entity(s: AgentScheduleModel) -> AgentSchedule:
        inp = dict(s.input) if s.input is not None else {}
        return AgentSchedule(
            id=s.id,
            agent_id=s.agent_id,
            user_id=s.user_id,
            alias=s.alias,
            cron_expression=s.cron_expression,
            input=inp,
            enabled=bool(s.enabled),
            last_run_at=s.last_run_at,
            next_run_at=s.next_run_at,
            created_at=s.created_at,
        )

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
        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            raise ValueError("Agent not found or unauthorized")
        row = AgentScheduleModel(
            agent_id=agent_id,
            user_id=user_id,
            alias=alias,
            cron_expression=cron_expression,
            input=dict(input_payload),
            enabled=enabled,
            next_run_at=next_run_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._schedule_to_entity(row)

    async def get_schedule(
        self, agent_id: UUID, user_id: UUID, schedule_id: UUID
    ) -> AgentSchedule | None:
        row = await self._session.get(AgentScheduleModel, schedule_id)
        if row is None or row.agent_id != agent_id or row.user_id != user_id:
            return None
        return self._schedule_to_entity(row)

    async def list_schedules(self, agent_id: UUID, user_id: UUID) -> list[AgentSchedule]:
        q = await self._session.execute(
            select(AgentScheduleModel)
            .join(AgentModel, AgentModel.id == AgentScheduleModel.agent_id)
            .where(AgentScheduleModel.agent_id == agent_id, AgentModel.user_id == user_id)
            .order_by(AgentScheduleModel.created_at.desc())
        )
        return [self._schedule_to_entity(r) for r in q.scalars().all()]

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
        row = await self._session.get(AgentScheduleModel, schedule_id)
        if row is None or row.agent_id != agent_id or row.user_id != user_id:
            return None
        if cron_expression is not None:
            row.cron_expression = cron_expression
        if input_payload is not None:
            row.input = dict(input_payload)
        if set_alias:
            row.alias = alias
        if enabled is not None:
            row.enabled = enabled
        await self._session.flush()
        now = datetime.now(UTC)
        if cron_expression is not None:
            row.next_run_at = next_fire_after(row.cron_expression, now)
        elif enabled is True and row.next_run_at <= now:
            row.next_run_at = next_fire_after(row.cron_expression, now)
        await self._session.flush()
        await self._session.refresh(row)
        return self._schedule_to_entity(row)

    async def delete_schedule(self, agent_id: UUID, user_id: UUID, schedule_id: UUID) -> bool:
        row = await self._session.get(AgentScheduleModel, schedule_id)
        if row is None or row.agent_id != agent_id or row.user_id != user_id:
            return False
        await self._session.delete(row)
        return True

    async def list_due_schedules(self, before: datetime, *, limit: int = 50) -> list[AgentSchedule]:
        q = await self._session.execute(
            select(AgentScheduleModel)
            .where(
                AgentScheduleModel.enabled.is_(True),
                AgentScheduleModel.next_run_at <= before,
            )
            .order_by(AgentScheduleModel.next_run_at.asc())
            .limit(limit)
        )
        return [self._schedule_to_entity(r) for r in q.scalars().all()]

    async def update_schedule_run_times(
        self,
        schedule_id: UUID,
        *,
        last_run_at: datetime,
        next_run_at: datetime,
    ) -> None:
        await self._session.execute(
            update(AgentScheduleModel)
            .where(AgentScheduleModel.id == schedule_id)
            .values(last_run_at=last_run_at, next_run_at=next_run_at)
        )

    async def set_alias(
        self, agent_id: UUID, user_id: UUID, name: str, version_number: int
    ) -> None:
        from app.infrastructure.persistence.postgres.models import AgentAliasModel

        m = await self._session.get(AgentModel, agent_id)
        if m is None or m.user_id != user_id:
            raise ValueError("Agent not found or unauthorized")

        q = await self._session.execute(
            select(AgentAliasModel).where(
                AgentAliasModel.agent_id == agent_id, AgentAliasModel.name == name
            )
        )
        alias = q.scalar_one_or_none()
        if alias:
            alias.version_number = version_number
        else:
            new_alias = AgentAliasModel(agent_id=agent_id, name=name, version_number=version_number)
            self._session.add(new_alias)
        await self._session.flush()

    async def get_alias(self, agent_id: UUID, user_id: UUID, name: str) -> int | None:
        from app.infrastructure.persistence.postgres.models import AgentAliasModel

        q = await self._session.execute(
            select(AgentAliasModel)
            .join(AgentModel, AgentModel.id == AgentAliasModel.agent_id)
            .where(
                AgentAliasModel.agent_id == agent_id,
                AgentAliasModel.name == name,
                AgentModel.user_id == user_id,
            )
        )
        alias = q.scalar_one_or_none()
        return alias.version_number if alias else None

    async def list_aliases(self, agent_id: UUID, user_id: UUID) -> dict[str, int]:
        from app.infrastructure.persistence.postgres.models import AgentAliasModel

        q = await self._session.execute(
            select(AgentAliasModel)
            .join(AgentModel, AgentModel.id == AgentAliasModel.agent_id)
            .where(AgentAliasModel.agent_id == agent_id, AgentModel.user_id == user_id)
        )
        return {alias.name: alias.version_number for alias in q.scalars().all()}
