import asyncio
import logging
import uuid
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from pydantic import ValidationError

from app.domain.entities.agent import Agent
from app.domain.entities.execution import Execution
from app.domain.exceptions import (
    AgentNotFoundError,
    ExecutionNotFoundError,
    ExecutionNotResumableError,
    InvalidGraphDefinitionError,
    StreamingNotAvailableError,
)
from app.domain.graph_definition import parse_and_validate_graph
from app.domain.ports.agent_orchestrator import AgentOrchestrator
from app.domain.ports.agent_repository import AgentRepository
from app.domain.ports.execution_events import ExecutionEventEmitter, NullExecutionEmitter
from app.infrastructure.events.redis_execution_stream import (
    RedisStreamEmitter,
    execution_stream_key,
)
from app.infrastructure.orchestration.checkpoint_registry import pop_saver
from app.infrastructure.persistence.postgres.agent_repo import PostgresAgentRepository
from app.infrastructure.persistence.postgres.session import get_session_factory

log = logging.getLogger(__name__)


def _normalize_graph(graph_definition: dict[str, Any]) -> dict[str, Any]:
    try:
        return parse_and_validate_graph(graph_definition)
    except (ValueError, ValidationError) as e:
        raise InvalidGraphDefinitionError(str(e)) from e


def _resume_value_from_decisions(decisions: list[dict[str, Any]]) -> Any:
    if not decisions:
        return "approve"
    d0 = decisions[0]
    if isinstance(d0, dict) and "type" in d0:
        return d0["type"]
    return d0


class AgentService:
    def __init__(
        self,
        repo: AgentRepository,
        orchestrator: AgentOrchestrator,
        redis_client: redis.Redis | None = None,
    ) -> None:
        self._repo = repo
        self._orchestrator = orchestrator
        self._redis = redis_client

    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        graph_definition: dict[str, Any],
        model_config: dict[str, Any],
    ) -> Agent:
        gd = _normalize_graph(graph_definition)
        return await self._repo.create(
            user_id=user_id,
            name=name,
            description=description,
            graph_definition=gd,
            model_config=model_config,
        )

    async def list_agents(self, user_id: UUID) -> list[Agent]:
        return await self._repo.list_for_user(user_id)

    async def get(self, agent_id: UUID, user_id: UUID) -> Agent:
        a = await self._repo.get_by_id(agent_id, user_id)
        if a is None:
            raise AgentNotFoundError(str(agent_id))
        return a

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
    ) -> Agent:
        gd = _normalize_graph(graph_definition) if graph_definition is not None else None
        a = await self._repo.update(
            agent_id,
            user_id,
            name,
            description,
            gd,
            model_config,
            status,
            interrupt_config=interrupt_config,
        )
        if a is None:
            raise AgentNotFoundError(str(agent_id))
        return a

    async def delete(self, agent_id: UUID, user_id: UUID) -> None:
        ok = await self._repo.delete(agent_id, user_id)
        if not ok:
            raise AgentNotFoundError(str(agent_id))

    def _make_emitter(self, execution_id: UUID) -> ExecutionEventEmitter:
        if self._redis is None:
            return NullExecutionEmitter()
        return RedisStreamEmitter(self._redis, execution_stream_key(execution_id))

    async def execute(
        self,
        agent_id: UUID,
        user_id: UUID,
        input_messages: list[dict[str, Any]],
        *,
        run_async: bool = False,
    ) -> Execution:
        agent = await self._repo.get_by_id(agent_id, user_id)
        if agent is None:
            raise AgentNotFoundError(str(agent_id))
        thread_id = str(uuid.uuid4())
        execution = await self._repo.create_execution(
            agent_id=agent_id,
            user_id=user_id,
            thread_id=thread_id,
            input_messages=input_messages,
        )

        if run_async:
            if self._redis is None:
                raise StreamingNotAvailableError()
            asyncio.create_task(
                self._execute_background(execution.id, agent_id, user_id, input_messages),
                name=f"exec-{execution.id}",
            )
            out = await self._repo.get_execution(agent_id, execution.id, user_id)
            assert out is not None
            return out

        emitter = self._make_emitter(execution.id)
        try:
            orch = await self._orchestrator.run(
                agent_id=agent_id,
                graph_definition=agent.graph_definition,
                model_config=agent.model_config,
                input_messages=input_messages,
                emitter=emitter,
                agent_label=agent.name,
                execution_id=execution.id,
            )
        except Exception:
            pop_saver(execution.id)
            raise
        if orch.interrupt_payload is not None:
            await self._repo.update_execution(
                execution.id,
                status="paused",
                output_messages=orch.output_messages,
                token_usage=orch.token_usage,
                duration_ms=orch.duration_ms,
                interrupt_state=orch.interrupt_payload,
            )
        else:
            await self._repo.update_execution(
                execution.id,
                status="completed",
                output_messages=orch.output_messages,
                token_usage=orch.token_usage,
                duration_ms=orch.duration_ms,
                completed_at=True,
            )
        final = await self._repo.get_execution(agent_id, execution.id, user_id)
        assert final is not None
        return final

    async def _execute_background(
        self,
        execution_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        input_messages: list[dict[str, Any]],
    ) -> None:
        factory = get_session_factory()
        emitter: ExecutionEventEmitter = (
            RedisStreamEmitter(self._redis, execution_stream_key(execution_id))
            if self._redis
            else NullExecutionEmitter()
        )
        try:
            async with factory() as session:
                repo = PostgresAgentRepository(session)
                agent = await repo.get_by_id(agent_id, user_id)
                if agent is None:
                    await emitter.emit("error", {"message": "Agent not found"})
                    await repo.update_execution(execution_id, status="failed", completed_at=True)
                    await session.commit()
                    return
                try:
                    orch = await self._orchestrator.run(
                        agent_id=agent_id,
                        graph_definition=agent.graph_definition,
                        model_config=agent.model_config,
                        input_messages=input_messages,
                        emitter=emitter,
                        agent_label=agent.name,
                        execution_id=execution_id,
                    )
                except Exception:
                    pop_saver(execution_id)
                    raise
                if orch.interrupt_payload is not None:
                    await repo.update_execution(
                        execution_id,
                        status="paused",
                        output_messages=orch.output_messages,
                        token_usage=orch.token_usage,
                        duration_ms=orch.duration_ms,
                        interrupt_state=orch.interrupt_payload,
                    )
                else:
                    await repo.update_execution(
                        execution_id,
                        status="completed",
                        output_messages=orch.output_messages,
                        token_usage=orch.token_usage,
                        duration_ms=orch.duration_ms,
                        completed_at=True,
                    )
                await session.commit()
        except Exception as e:
            log.exception("background_execution_failed", extra={"execution_id": str(execution_id)})
            try:
                async with factory() as session:
                    repo = PostgresAgentRepository(session)
                    await repo.update_execution(
                        execution_id,
                        status="failed",
                        completed_at=True,
                    )
                    await session.commit()
            except Exception:
                log.exception("failed_to_mark_execution_failed")
            try:
                await emitter.emit("error", {"message": str(e), "type": type(e).__name__})
            except Exception:
                log.exception("failed_to_emit_error_event")

    async def resume_execution(
        self,
        agent_id: UUID,
        execution_id: UUID,
        user_id: UUID,
        decisions: list[dict[str, Any]],
    ) -> Execution:
        agent = await self._repo.get_by_id(agent_id, user_id)
        if agent is None:
            raise AgentNotFoundError(str(agent_id))
        ex = await self._repo.get_execution(agent_id, execution_id, user_id)
        if ex is None:
            raise ExecutionNotFoundError(str(execution_id))
        if ex.status != "paused":
            raise ExecutionNotResumableError("Execution is not paused for human input")
        emitter = self._make_emitter(execution_id)
        resume_val = _resume_value_from_decisions(decisions)
        try:
            orch = await self._orchestrator.resume(
                execution_id=execution_id,
                agent_id=agent_id,
                graph_definition=agent.graph_definition,
                model_config=agent.model_config,
                resume_value=resume_val,
                emitter=emitter,
                agent_label=agent.name,
            )
        except Exception:
            pop_saver(execution_id)
            raise
        if orch.interrupt_payload is not None:
            merged = dict(ex.interrupt_state or {})
            merged["resume_chain"] = merged.get("resume_chain", []) + [resume_val]
            merged.update(orch.interrupt_payload)
            await self._repo.update_execution(
                execution_id,
                status="paused",
                output_messages=orch.output_messages,
                token_usage=orch.token_usage,
                duration_ms=orch.duration_ms,
                interrupt_state=merged,
            )
        else:
            await self._repo.update_execution(
                execution_id,
                status="completed",
                output_messages=orch.output_messages,
                token_usage=orch.token_usage,
                duration_ms=orch.duration_ms,
                clear_interrupt_state=True,
                completed_at=True,
            )
        final = await self._repo.get_execution(agent_id, execution_id, user_id)
        assert final is not None
        return final

    async def get_execution(self, agent_id: UUID, execution_id: UUID, user_id: UUID) -> Execution:
        e = await self._repo.get_execution(agent_id, execution_id, user_id)
        if e is None:
            raise ExecutionNotFoundError(str(execution_id))
        return e

    async def list_executions(self, agent_id: UUID, user_id: UUID) -> list[Execution]:
        await self.get(agent_id, user_id)
        return await self._repo.list_executions(agent_id, user_id)

    async def export_agent(self, agent_id: UUID, user_id: UUID) -> dict[str, Any]:
        a = await self.get(agent_id, user_id)
        return {
            "version": 1,
            "name": a.name,
            "description": a.description,
            "graph_definition": a.graph_definition,
            "model_config": a.model_config,
            "interrupt_config": a.interrupt_config,
            "skills": a.skills,
        }

    async def import_agent(
        self,
        user_id: UUID,
        payload: dict[str, Any],
        *,
        name_override: str | None = None,
    ) -> Agent:
        name = name_override or payload.get("name") or "Imported agent"
        desc = payload.get("description")
        gd = _normalize_graph(payload.get("graph_definition") or {})
        mc = payload.get("model_config") or payload.get("llm_model_config") or {}
        ic = payload.get("interrupt_config")
        base = await self._repo.create(
            user_id=user_id,
            name=name,
            description=desc,
            graph_definition=gd,
            model_config=mc,
        )
        if ic is not None:
            return await self.update(
                base.id,
                user_id,
                None,
                None,
                None,
                None,
                None,
                interrupt_config=ic,
            )
        return base
