import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from pydantic import ValidationError
from sqlalchemy import update as sa_update

from app.application.services.knowledge_service import KnowledgeService
from app.application.services.secrets_service import SecretsService
from app.domain.agent_diff import diff_agent_versions as compute_agent_diff
from app.domain.attached_skill_binding import AttachedSkillBinding
from app.domain.entities.agent import Agent
from app.domain.entities.agent_schedule import AgentSchedule
from app.domain.entities.execution import Execution
from app.domain.exceptions import (
    AgentNotFoundError,
    ExecutionNotFoundError,
    ExecutionNotResumableError,
    FinetuneJobNotFoundError,
    InvalidAgentSkillsError,
    InvalidGraphDefinitionError,
    InvalidSpeechFinetuneJobError,
    ScheduleNotFoundError,
    StreamingNotAvailableError,
)
from app.domain.execution_policy import parse_execution_policy
from app.domain.graph_definition import (
    GraphDefinitionValidated,
    GraphNode,
    parse_and_validate_graph,
)
from app.domain.ports.agent_orchestrator import AgentOrchestrator
from app.domain.ports.agent_repository import AgentRepository
from app.domain.ports.campaign_repository import CampaignRepository
from app.domain.ports.execution_events import ExecutionEventEmitter, NullExecutionEmitter
from app.domain.ports.finetune_repository import FinetuneJobRepository
from app.domain.ports.skill_repository import SkillRepository
from app.domain.ports.user_repository import UserRepository
from app.domain.schedule_cron import next_fire_after, validate_cron_expression
from app.domain.speech_example_flywheel import (
    SPEECH_EXAMPLE_FEEDBACK_MIN_SCORE,
    graph_has_asr_node,
    transcription_from_output_messages,
)
from app.domain.value_objects import AgentModelConfig, InterruptConfig, MessageDict
from app.infrastructure.events.redis_execution_stream import (
    RedisStreamEmitter,
    execution_stream_key,
)
from app.infrastructure.persistence.postgres.agent_repo import PostgresAgentRepository
from app.infrastructure.persistence.postgres.models import ConversationModel
from app.infrastructure.persistence.postgres.session import get_session_factory
from app.infrastructure.persistence.postgres.skill_repo import PostgresSkillRepository
from app.infrastructure.persistence.postgres.speech_example_repo import (
    PostgresSpeechExampleRepository,
)
from app.infrastructure.webhooks.delivery import schedule_execution_completed_webhook

log = logging.getLogger(__name__)


def _model_config_input_to_dict(model_config: AgentModelConfig | dict[str, Any]) -> dict[str, Any]:
    if isinstance(model_config, AgentModelConfig):
        return model_config.model_dump()
    return dict(model_config)


def _normalize_graph(
    graph_definition: GraphDefinitionValidated | dict[str, Any],
) -> GraphDefinitionValidated:
    if isinstance(graph_definition, GraphDefinitionValidated):
        return graph_definition
    try:
        return parse_and_validate_graph(graph_definition)
    except (ValueError, ValidationError) as e:
        raise InvalidGraphDefinitionError(str(e)) from e


def _input_audio_kw(graph_extra: dict[str, Any] | None) -> dict[str, str]:
    if not graph_extra:
        return {}
    b64 = graph_extra.get("audio_b64")
    if b64 is not None and str(b64).strip():
        return {"input_audio_b64": str(b64)}
    return {}


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
        skill_repo: SkillRepository,
        finetune_repo: FinetuneJobRepository | None = None,
        redis_client: redis.Redis | None = None,
        knowledge_service: KnowledgeService | None = None,
        secrets_service: SecretsService | None = None,
        campaign_repo: CampaignRepository | None = None,
        speech_example_repo: PostgresSpeechExampleRepository | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        self._repo = repo
        self._orchestrator = orchestrator
        self._skill_repo = skill_repo
        self._finetune_repo = finetune_repo
        self._redis = redis_client
        self._knowledge = knowledge_service
        self._secrets = secrets_service
        self._campaigns = campaign_repo
        self._speech_examples = speech_example_repo
        self._users = user_repo

    def _knowledge_fn(self, user_id: UUID):
        if self._knowledge is None:
            return None

        async def search_fn(query: str, top_k: int) -> str:
            return await self._knowledge.search_context(user_id, query, top_k)

        return search_fn

    def _make_subagent_resolver(self, repo: AgentRepository, user_id: UUID):
        async def resolve(subagent_id: UUID) -> Agent:
            agent = await repo.get_by_id(subagent_id, user_id)
            if agent is None:
                raise ValueError(f"Subagent {subagent_id} not found")
            return agent

        return resolve

    async def _normalize_attached_skills(self, user_id: UUID, skill_ids: list[str]) -> list[str]:
        """Deduplicate while preserving order; verify each skill is visible to the user."""
        seen: set[str] = set()
        out: list[str] = []
        for raw in skill_ids:
            try:
                sid = UUID(raw)
            except ValueError as e:
                raise InvalidAgentSkillsError(f"Invalid skill id: {raw!r}") from e
            sk = await self._skill_repo.get_by_id(sid, user_id)
            if sk is None:
                raise InvalidAgentSkillsError(f"Skill not found or not visible: {raw}")
            sid_str = str(sk.id)
            if sid_str not in seen:
                seen.add(sid_str)
                out.append(sid_str)
        return out

    async def _attached_skill_bindings(
        self,
        skill_repo: SkillRepository,
        user_id: UUID,
        skill_ids: list[str],
    ) -> list[AttachedSkillBinding]:
        out: list[AttachedSkillBinding] = []
        for sid in skill_ids:
            try:
                uid = UUID(sid)
            except ValueError:
                continue
            sk = await skill_repo.get_by_id(uid, user_id)
            if sk is None:
                continue
            out.append(
                AttachedSkillBinding(
                    name=sk.name,
                    skill_type=sk.skill_type,
                    source_code=sk.source_code,
                    instructions=sk.instructions,
                    security_validated=sk.security_validated,
                )
            )
        return out

    async def _enrich_finetuned_model_config(
        self, user_id: UUID, raw: dict[str, Any]
    ) -> dict[str, Any]:
        if str(raw.get("provider") or "").lower() != "finetuned":
            return raw
        job_id_raw = raw.get("finetune_job_id")
        if not job_id_raw or self._finetune_repo is None:
            return raw
        try:
            job_uuid = UUID(str(job_id_raw))
        except ValueError as e:
            raise FinetuneJobNotFoundError(str(job_id_raw)) from e
        job = await self._finetune_repo.get_by_id(job_uuid, user_id)
        if job is None:
            raise FinetuneJobNotFoundError(str(job_uuid))
        out = dict(raw)
        out["model"] = job.base_model
        return out

    async def _resolve_speech_finetune_endpoint(
        self,
        user_id: UUID,
        job_id_raw: Any,
        expected_modality: str,
    ) -> str:
        if self._finetune_repo is None:
            raise InvalidSpeechFinetuneJobError("Fine-tune repository is not configured")
        try:
            job_uuid = UUID(str(job_id_raw))
        except ValueError as e:
            raise FinetuneJobNotFoundError(str(job_id_raw)) from e
        job = await self._finetune_repo.get_by_id(job_uuid, user_id)
        if job is None:
            raise FinetuneJobNotFoundError(str(job_uuid))
        if job.status != "completed":
            raise InvalidSpeechFinetuneJobError(
                f"Speech fine-tune job {job_uuid} has status {job.status!r}, expected completed"
            )
        ep = (job.inference_endpoint or "").strip()
        if not ep:
            raise InvalidSpeechFinetuneJobError(
                f"Speech fine-tune job {job_uuid} has no inference endpoint"
            )
        if str(job.modality) != expected_modality:
            raise InvalidSpeechFinetuneJobError(
                f"Speech fine-tune job {job_uuid} has modality {job.modality!r}, "
                f"expected {expected_modality!r}"
            )
        return ep

    async def _enrich_finetuned_speech_graph(
        self, graph_def: GraphDefinitionValidated, user_id: UUID
    ) -> GraphDefinitionValidated:
        if self._finetune_repo is None:
            return graph_def
        new_nodes: list[GraphNode] = []
        for n in graph_def.nodes:
            cfg = dict(n.config)
            p = str(cfg.get("provider") or "").lower()
            ep_existing = (cfg.get("endpoint_url") or "").strip()

            if n.type == "asr" and p == "finetuned_whisper":
                jid = cfg.get("finetune_job_id")
                if jid and not ep_existing:
                    cfg["endpoint_url"] = await self._resolve_speech_finetune_endpoint(
                        user_id, jid, "whisper"
                    )
            elif n.type == "tts" and p == "finetuned_tts":
                jid = cfg.get("finetune_job_id")
                if jid and not ep_existing:
                    cfg["endpoint_url"] = await self._resolve_speech_finetune_endpoint(
                        user_id, jid, "tts_voice"
                    )
            new_nodes.append(GraphNode(id=n.id, type=n.type, config=cfg))
        return graph_def.model_copy(update={"nodes": new_nodes})

    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        graph_definition: dict[str, Any],
        model_config: dict[str, Any] | AgentModelConfig,
        skills: list[str] | None = None,
        execution_policy: dict[str, Any] | None = None,
        collect_speech_examples: bool | None = None,
    ) -> Agent:
        gd = _normalize_graph(graph_definition)
        resolved_skills = (
            await self._normalize_attached_skills(user_id, skills) if skills is not None else []
        )
        pol = (
            parse_execution_policy(execution_policy).to_dict()
            if execution_policy is not None
            else {}
        )
        mc_dict = _model_config_input_to_dict(model_config)
        enriched = await self._enrich_finetuned_model_config(user_id, mc_dict)
        return await self._repo.create(
            user_id=user_id,
            name=name,
            description=description,
            graph_definition=gd,
            model_config=AgentModelConfig.model_validate(enriched),
            skills=resolved_skills,
            execution_policy=pol,
            collect_speech_examples=collect_speech_examples,
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
        model_config: dict[str, Any] | AgentModelConfig | None,
        status: str | None,
        interrupt_config: dict[str, Any] | None = None,
        skills: list[str] | None = None,
        execution_policy: dict[str, Any] | None = None,
        collect_speech_examples: bool | None = None,
    ) -> Agent:
        gd = _normalize_graph(graph_definition) if graph_definition is not None else None
        mc: AgentModelConfig | None = None
        if model_config is not None:
            mc_dict = _model_config_input_to_dict(model_config)
            enriched = await self._enrich_finetuned_model_config(user_id, mc_dict)
            mc = AgentModelConfig.model_validate(enriched)
        ic = (
            InterruptConfig.model_validate(interrupt_config)
            if interrupt_config is not None
            else None
        )
        resolved_skills = (
            await self._normalize_attached_skills(user_id, skills) if skills is not None else None
        )
        pol = (
            parse_execution_policy(execution_policy).to_dict()
            if execution_policy is not None
            else None
        )
        a = await self._repo.update(
            agent_id,
            user_id,
            name,
            description,
            gd,
            mc,
            status,
            interrupt_config=ic,
            skills=resolved_skills,
            execution_policy=pol,
            collect_speech_examples=collect_speech_examples,
        )
        if a is None:
            raise AgentNotFoundError(str(agent_id))
        return a

    async def delete(self, agent_id: UUID, user_id: UUID) -> None:
        ok = await self._repo.delete(agent_id, user_id)
        if not ok:
            raise AgentNotFoundError(str(agent_id))

    def _make_emitter(self, execution_id: UUID) -> ExecutionEventEmitter:
        from app.config import get_settings

        settings = get_settings()

        inner = (
            RedisStreamEmitter(self._redis, execution_stream_key(execution_id))
            if self._redis
            else NullExecutionEmitter()
        )

        backend = settings.observability_backend
        trace_id = str(execution_id)

        use_langfuse = backend in ("langfuse", "both")
        use_langsmith = backend in ("langsmith", "both")

        emitter = inner

        # Wrap with Langfuse typed spans if configured
        if use_langfuse and settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                from app.infrastructure.observability.langfuse_span_emitter import (
                    LangfuseSpanEmitter,
                )

                emitter = LangfuseSpanEmitter(emitter, trace_id=trace_id)
            except Exception:
                pass

        # Wrap with LangSmith typed spans if configured
        if use_langsmith and settings.langsmith_api_key:
            try:
                from app.infrastructure.observability.langsmith_span_emitter import (
                    LangsmithSpanEmitter,
                )

                emitter = LangsmithSpanEmitter(
                    emitter,
                    trace_id=trace_id,
                    api_key=settings.langsmith_api_key,
                    project=settings.langsmith_project,
                )
            except Exception:
                pass

        return emitter

    async def execute(
        self,
        agent_id: UUID,
        user_id: UUID,
        input_messages: list[dict[str, Any]],
        *,
        run_async: bool = False,
        version: int | None = None,
        alias: str | None = None,
        graph_extra: dict[str, Any] | None = None,
        trigger_source: str = "api",
        schedule_id: UUID | None = None,
        thread_id: str | None = None,
    ) -> Execution:
        agent = await self._repo.get_by_id(agent_id, user_id)
        if agent is None:
            raise AgentNotFoundError(str(agent_id))
        conversation_thread_id = thread_id  # preserve caller-supplied thread_id for conv update
        thread_id = thread_id if thread_id is not None else str(uuid.uuid4())
        typed_msgs = [MessageDict.model_validate(m) for m in input_messages]

        ver_for_exec = None
        if alias is not None:
            ver_for_exec = await self._repo.get_alias(agent_id, user_id, alias)
            if ver_for_exec is None:
                raise ValueError(f"Alias '{alias}' not found for agent")
        elif version is not None:
            ver_for_exec = version

        if ver_for_exec is not None:
            repo_pg = self._postgres_repo()
            v_snapshot = await repo_pg.get_version(agent_id, user_id, ver_for_exec)
            if v_snapshot is None:
                raise ValueError(f"Version {ver_for_exec} not found for agent")
            graph_def = _normalize_graph(v_snapshot.graph_definition)
            model_cfg = AgentModelConfig.model_validate(v_snapshot.model_config)
            skills = v_snapshot.skills
            exec_policy = parse_execution_policy(v_snapshot.execution_policy)
        else:
            latest_v = await self._repo.get_latest_version_number(agent_id)
            ver_for_exec = latest_v if latest_v > 0 else None
            graph_def = agent.graph_definition
            model_cfg = agent.model_config
            skills = agent.skills
            exec_policy = agent.execution_policy

        execution = await self._repo.create_execution(
            agent_id=agent_id,
            user_id=user_id,
            thread_id=thread_id,
            input_messages=typed_msgs,
            agent_version_number=ver_for_exec,
            trigger_source=trigger_source,
            schedule_id=schedule_id,
        )

        if run_async:
            if self._redis is None:
                raise StreamingNotAvailableError()
            asyncio.create_task(
                self._execute_background(
                    execution.id,
                    agent_id,
                    user_id,
                    input_messages,
                    ver_for_exec,
                    graph_extra=graph_extra,
                ),
                name=f"exec-{execution.id}",
            )
            out = await self._repo.get_execution(agent_id, execution.id, user_id)
            assert out is not None
            return out

        emitter = self._make_emitter(execution.id)
        attached = await self._attached_skill_bindings(self._skill_repo, user_id, skills)
        user_secrets = await self._secrets.get_decrypted_secrets(user_id) if self._secrets else {}

        graph_def = await self._enrich_finetuned_speech_graph(graph_def, user_id)
        try:
            orch = await self._orchestrator.run(
                agent_id=agent_id,
                graph_definition=graph_def,
                model_config=model_cfg,
                input_messages=typed_msgs,
                emitter=emitter,
                agent_label=agent.name,
                execution_id=execution.id,
                attached_skills=attached,
                knowledge_search=self._knowledge_fn(user_id),
                openai_key=user_secrets.get("openai_key"),
                google_key=user_secrets.get("google_key"),
                anthropic_key=user_secrets.get("anthropic_key"),
                subagent_resolver=self._make_subagent_resolver(self._repo, user_id),
                execution_policy=exec_policy,
                graph_extra=graph_extra,
            )
        except Exception:
            raise
        audio_kw = (
            {"output_audio_b64": orch.output_audio_b64} if orch.output_audio_b64 is not None else {}
        )
        in_audio_kw = _input_audio_kw(graph_extra)
        if orch.interrupt_payload is not None:
            await self._repo.update_execution(
                execution.id,
                status="paused",
                output_messages=orch.output_messages,
                token_usage=orch.token_usage,
                duration_ms=orch.duration_ms,
                interrupt_state=orch.interrupt_payload,
                **audio_kw,
                **in_audio_kw,
            )
        else:
            await self._repo.update_execution(
                execution.id,
                status="completed",
                output_messages=orch.output_messages,
                token_usage=orch.token_usage,
                duration_ms=orch.duration_ms,
                completed_at=True,
                **audio_kw,
                **in_audio_kw,
            )
            schedule_execution_completed_webhook(
                user_id,
                {
                    "execution_id": str(execution.id),
                    "agent_id": str(agent_id),
                    "status": "completed",
                    "duration_ms": orch.duration_ms,
                    "token_usage": orch.token_usage,
                },
            )
            await emitter.emit(
                "complete",
                {
                    "agent_id": str(agent_id),
                    "agent_name": agent.name,
                    "total_duration_ms": orch.duration_ms,
                    "message_count": len(orch.output_messages),
                },
            )
        if conversation_thread_id:
            try:
                session_factory = get_session_factory()
                async with session_factory() as _session:
                    await _session.execute(
                        sa_update(ConversationModel)
                        .where(ConversationModel.thread_id == conversation_thread_id)
                        .values(
                            last_message_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                            message_count=ConversationModel.message_count + 1,
                        )
                    )
                    await _session.commit()
            except Exception:
                pass  # conversation update is best-effort

        final = await self._repo.get_execution(agent_id, execution.id, user_id)
        assert final is not None
        return final

    async def _execute_background(
        self,
        execution_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        input_messages: list[dict[str, Any]],
        ver_for_exec: int | None = None,
        *,
        graph_extra: dict[str, Any] | None = None,
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
                skill_repo = PostgresSkillRepository(session)
                agent = await repo.get_by_id(agent_id, user_id)
                if agent is None:
                    await emitter.emit("error", {"message": "Agent not found"})
                    await repo.update_execution(execution_id, status="failed", completed_at=True)
                    await session.commit()
                    return
                if ver_for_exec is not None:
                    v_snapshot = await repo.get_version(agent_id, user_id, ver_for_exec)
                    if v_snapshot:
                        graph_def = _normalize_graph(v_snapshot.graph_definition)
                        model_cfg = AgentModelConfig.model_validate(v_snapshot.model_config)
                        skills = v_snapshot.skills
                        exec_policy = parse_execution_policy(v_snapshot.execution_policy)
                    else:
                        graph_def = agent.graph_definition
                        model_cfg = agent.model_config
                        skills = agent.skills
                        exec_policy = agent.execution_policy
                else:
                    graph_def = agent.graph_definition
                    model_cfg = agent.model_config
                    skills = agent.skills
                    exec_policy = agent.execution_policy

                typed_msgs = [MessageDict.model_validate(m) for m in input_messages]
                attached = await self._attached_skill_bindings(skill_repo, user_id, skills)
                user_secrets = (
                    await self._secrets.get_decrypted_secrets(user_id) if self._secrets else {}
                )
                graph_def = await self._enrich_finetuned_speech_graph(graph_def, user_id)
                try:
                    orch = await self._orchestrator.run(
                        agent_id=agent_id,
                        graph_definition=graph_def,
                        model_config=model_cfg,
                        input_messages=typed_msgs,
                        emitter=emitter,
                        agent_label=agent.name,
                        execution_id=execution_id,
                        attached_skills=attached,
                        knowledge_search=self._knowledge_fn(user_id),
                        openai_key=user_secrets.get("openai_key"),
                        google_key=user_secrets.get("google_key"),
                        anthropic_key=user_secrets.get("anthropic_key"),
                        subagent_resolver=self._make_subagent_resolver(repo, user_id),
                        execution_policy=exec_policy,
                        graph_extra=graph_extra,
                    )
                except Exception:
                    raise
                audio_kw = (
                    {"output_audio_b64": orch.output_audio_b64}
                    if orch.output_audio_b64 is not None
                    else {}
                )
                in_audio_kw = _input_audio_kw(graph_extra)
                if orch.interrupt_payload is not None:
                    await repo.update_execution(
                        execution_id,
                        status="paused",
                        output_messages=orch.output_messages,
                        token_usage=orch.token_usage,
                        duration_ms=orch.duration_ms,
                        interrupt_state=orch.interrupt_payload,
                        **audio_kw,
                        **in_audio_kw,
                    )
                else:
                    await repo.update_execution(
                        execution_id,
                        status="completed",
                        output_messages=orch.output_messages,
                        token_usage=orch.token_usage,
                        duration_ms=orch.duration_ms,
                        completed_at=True,
                        **audio_kw,
                        **in_audio_kw,
                    )
                    schedule_execution_completed_webhook(
                        user_id,
                        {
                            "execution_id": str(execution_id),
                            "agent_id": str(agent_id),
                            "status": "completed",
                            "duration_ms": orch.duration_ms,
                            "token_usage": orch.token_usage,
                        },
                    )
                    await emitter.emit(
                        "complete",
                        {
                            "agent_id": str(agent_id),
                            "agent_name": agent.name,
                            "total_duration_ms": orch.duration_ms,
                            "message_count": len(orch.output_messages),
                        },
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
        attached = await self._attached_skill_bindings(self._skill_repo, user_id, agent.skills)
        user_secrets = await self._secrets.get_decrypted_secrets(user_id) if self._secrets else {}

        graph_def_resume = await self._enrich_finetuned_speech_graph(
            agent.graph_definition, user_id
        )
        try:
            orch = await self._orchestrator.resume(
                execution_id=execution_id,
                agent_id=agent_id,
                graph_definition=graph_def_resume,
                model_config=agent.model_config,
                resume_value=resume_val,
                emitter=emitter,
                agent_label=agent.name,
                attached_skills=attached,
                knowledge_search=self._knowledge_fn(user_id),
                openai_key=user_secrets.get("openai_key"),
                google_key=user_secrets.get("google_key"),
                anthropic_key=user_secrets.get("anthropic_key"),
                subagent_resolver=self._make_subagent_resolver(self._repo, user_id),
                execution_policy=agent.execution_policy,
            )
        except Exception:
            raise
        audio_kw = (
            {"output_audio_b64": orch.output_audio_b64} if orch.output_audio_b64 is not None else {}
        )
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
                **audio_kw,
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
                **audio_kw,
            )
            schedule_execution_completed_webhook(
                user_id,
                {
                    "execution_id": str(execution_id),
                    "agent_id": str(agent_id),
                    "status": "completed",
                    "duration_ms": orch.duration_ms,
                    "token_usage": orch.token_usage,
                },
            )
            await emitter.emit(
                "complete",
                {
                    "agent_id": str(agent_id),
                    "agent_name": agent.name,
                    "total_duration_ms": orch.duration_ms,
                    "message_count": len(orch.output_messages),
                },
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

    async def create_schedule(
        self,
        agent_id: UUID,
        user_id: UUID,
        cron_expression: str,
        input_payload: dict[str, Any],
        *,
        alias: str | None = None,
        enabled: bool = True,
    ) -> AgentSchedule:
        await self.get(agent_id, user_id)
        validate_cron_expression(cron_expression)
        now = datetime.now(UTC)
        next_at = next_fire_after(cron_expression, now)
        return await self._repo.create_schedule(
            agent_id,
            user_id,
            cron_expression,
            input_payload,
            alias=alias,
            enabled=enabled,
            next_run_at=next_at,
        )

    async def list_schedules(self, agent_id: UUID, user_id: UUID) -> list[AgentSchedule]:
        await self.get(agent_id, user_id)
        return await self._repo.list_schedules(agent_id, user_id)

    async def get_schedule(self, agent_id: UUID, user_id: UUID, schedule_id: UUID) -> AgentSchedule:
        await self.get(agent_id, user_id)
        s = await self._repo.get_schedule(agent_id, user_id, schedule_id)
        if s is None:
            raise ScheduleNotFoundError(str(schedule_id))
        return s

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
    ) -> AgentSchedule:
        await self.get(agent_id, user_id)
        if cron_expression is not None:
            validate_cron_expression(cron_expression)
        out = await self._repo.update_schedule(
            agent_id,
            user_id,
            schedule_id,
            cron_expression=cron_expression,
            input_payload=input_payload,
            set_alias=set_alias,
            alias=alias,
            enabled=enabled,
        )
        if out is None:
            raise ScheduleNotFoundError(str(schedule_id))
        return out

    async def delete_schedule(self, agent_id: UUID, user_id: UUID, schedule_id: UUID) -> None:
        await self.get(agent_id, user_id)
        ok = await self._repo.delete_schedule(agent_id, user_id, schedule_id)
        if not ok:
            raise ScheduleNotFoundError(str(schedule_id))

    async def submit_execution_feedback(
        self,
        agent_id: UUID,
        execution_id: UUID,
        user_id: UUID,
        *,
        score: float,
        comment: str | None,
    ) -> None:
        """Attach user feedback to the LangSmith run rooted at execution_id."""
        ex = await self.get_execution(agent_id, execution_id, user_id)
        if ex.status == "running":
            raise ValueError("Execution is still running")

        try:
            from langsmith import Client
        except ImportError as e:
            raise RuntimeError("langsmith is not installed") from e

        client = Client()
        client.create_feedback(
            run_id=execution_id,
            key="user_score",
            score=float(score),
            trace_id=execution_id,
            comment=comment,
        )

        # Data Flywheel: Automatically save highly rated executions for fine-tuning
        if score >= 0.8 and self._finetune_repo is not None:
            input_msgs = [m.to_dict() for m in ex.input_messages]
            output_msgs = [m.to_dict() for m in (ex.output_messages or [])]
            if input_msgs and output_msgs:
                await self._finetune_repo.create_example(
                    agent_id=agent_id,
                    user_id=user_id,
                    execution_id=execution_id,
                    input_messages=input_msgs,
                    output_messages=output_msgs,
                    score=float(score),
                )

        await self._maybe_collect_speech_example_from_feedback(
            agent_id, execution_id, user_id, float(score)
        )

    async def _maybe_collect_speech_example_from_feedback(
        self,
        agent_id: UUID,
        execution_id: UUID,
        user_id: UUID,
        score: float,
    ) -> None:
        if self._speech_examples is None or self._users is None:
            return
        if score < SPEECH_EXAMPLE_FEEDBACK_MIN_SCORE:
            return
        user = await self._users.get_by_id(user_id)
        agent = await self._repo.get_by_id(agent_id, user_id)
        if user is None or agent is None:
            return
        if not (user.collect_speech_examples or agent.collect_speech_examples):
            return
        if not graph_has_asr_node(agent.graph_definition):
            return
        ex = await self._repo.get_execution(agent_id, execution_id, user_id)
        if ex is None:
            return
        audio = ex.input_audio_b64
        if not audio or not str(audio).strip():
            return
        text = transcription_from_output_messages(ex.output_messages)
        if not text.strip():
            return
        try:
            await self._speech_examples.create(
                user_id=user_id,
                audio_b64=str(audio),
                transcription=text,
                agent_id=agent_id,
                execution_id=execution_id,
                score=score,
                metadata={"source": "execution_feedback"},
            )
        except Exception:
            log.exception(
                "speech_example_collect_failed",
                extra={"execution_id": str(execution_id)},
            )

    def _postgres_repo(self) -> PostgresAgentRepository:
        if not isinstance(self._repo, PostgresAgentRepository):
            raise TypeError("This operation requires the PostgreSQL agent repository")
        return self._repo

    async def diff_agent_versions(
        self,
        agent_id: UUID,
        user_id: UUID,
        from_version: int,
        to_version: int,
    ) -> dict[str, Any]:
        repo = self._postgres_repo()
        await self.get(agent_id, user_id)
        v_from = await repo.get_version(agent_id, user_id, from_version)
        v_to = await repo.get_version(agent_id, user_id, to_version)
        if v_from is None or v_to is None:
            raise ValueError("One or both versions were not found")
        left = {
            "graph_definition": v_from.graph_definition,
            "model_config": v_from.model_config,
            "skills": v_from.skills,
            "execution_policy": v_from.execution_policy,
        }
        right = {
            "graph_definition": v_to.graph_definition,
            "model_config": v_to.model_config,
            "skills": v_to.skills,
            "execution_policy": v_to.execution_policy,
        }
        return compute_agent_diff(
            left, right, left_label=f"v{from_version}", right_label=f"v{to_version}"
        )

    async def get_version_stats(self, agent_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        repo = self._postgres_repo()
        await self.get(agent_id, user_id)  # verify agent exists and belongs to user
        return await repo.execution_stats_by_version(agent_id, user_id)

    async def get_agent_scorecard(self, agent_id: UUID, user_id: UUID) -> dict[str, Any]:
        repo = self._postgres_repo()
        await self.get(agent_id, user_id)
        versions = await repo.list_versions(agent_id, user_id)
        exec_stats = await repo.execution_stats_by_version(agent_id, user_id)
        campaigns: list[dict[str, Any]] = []
        if self._campaigns is not None:
            raw = await self._campaigns.list_for_agent(agent_id, user_id)
            for c in raw[:15]:
                campaigns.append(
                    {
                        "id": str(c.id),
                        "status": c.status,
                        "overall_score": c.overall_score,
                        "total_tests": c.total_tests,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                )
        return {
            "agent_id": str(agent_id),
            "versions": [
                {
                    "version_number": v.version_number,
                    "created_at": v.created_at.isoformat(),
                    "change_note": v.change_note,
                }
                for v in versions
            ],
            "executions_by_agent_version": exec_stats,
            "recent_campaigns": campaigns,
        }

    async def export_agent(
        self,
        agent_id: UUID,
        user_id: UUID,
        *,
        include_skills: bool = False,
        version: int | None = None,
        alias: str | None = None,
    ) -> dict[str, Any]:
        import hashlib

        agent = await self.get(agent_id, user_id)

        ver_for_exec = None
        if alias is not None:
            ver_for_exec = await self._repo.get_alias(agent_id, user_id, alias)
            if ver_for_exec is None:
                raise ValueError(f"Alias '{alias}' not found for agent")
        elif version is not None:
            ver_for_exec = version

        if ver_for_exec is not None:
            repo_pg = self._postgres_repo()
            v_snapshot = await repo_pg.get_version(agent_id, user_id, ver_for_exec)
            if v_snapshot is None:
                raise ValueError(f"Version {ver_for_exec} not found for agent")
            graph_def = _normalize_graph(v_snapshot.graph_definition)
            model_cfg = AgentModelConfig.model_validate(v_snapshot.model_config)
            skills = v_snapshot.skills
            exec_policy = parse_execution_policy(v_snapshot.execution_policy)
            interrupt_cfg = (
                InterruptConfig()
            )  # Version snapshots don't store interrupt config natively, fallback empty
        else:
            graph_def = agent.graph_definition
            model_cfg = agent.model_config
            skills = agent.skills
            exec_policy = agent.execution_policy
            interrupt_cfg = agent.interrupt_config

        skills_data: list[Any]
        if include_skills and skills:
            resolved = []
            for skill_id_str in skills:
                try:
                    sk = await self._skill_repo.get_by_id(UUID(skill_id_str), user_id)
                    if sk:
                        skill_dict: dict[str, Any] = {
                            "id": str(sk.id),
                            "name": sk.name,
                            "description": sk.description,
                            "skill_type": sk.skill_type,
                            "source_code": sk.source_code,
                            "instructions": sk.instructions,
                            "parameters_schema": sk.parameters_schema.to_dict()
                            if sk.parameters_schema
                            else None,
                            "permissions": sk.permissions,
                            "source_sha256": sk.source_sha256,
                            "security_validated": sk.security_validated,
                        }
                        if sk.source_code:
                            skill_dict["sha256"] = hashlib.sha256(
                                sk.source_code.encode()
                            ).hexdigest()
                        resolved.append(skill_dict)
                    else:
                        resolved.append(skill_id_str)  # fallback: keep UUID if skill not found
                except Exception:
                    resolved.append(skill_id_str)
            skills_data = resolved
        else:
            skills_data = skills or []

        return {
            "version": 2,  # bump version to signal enriched format
            "name": agent.name,
            "description": agent.description,
            "graph_definition": graph_def.to_dict(),
            "model_config": model_cfg.to_dict(),
            "interrupt_config": interrupt_cfg.to_dict(),
            "execution_policy": exec_policy.to_dict(),
            "skills": skills_data,
        }

    async def import_yaml(
        self, user_id: UUID, yaml_content: str, *, name_override: str | None = None
    ):
        import yaml

        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")

        if not isinstance(data, dict):
            raise ValueError("YAML must represent a dictionary")

        # Reformat top-level nodes/edges into graph_definition if not already nested
        if "nodes" in data and "graph_definition" not in data:
            data["graph_definition"] = {
                "nodes": data.pop("nodes"),
                "edges": data.pop("edges", []),
                "entry_point": data.pop("entry_point", None),
            }

        return await self.import_agent(user_id, data, name_override=name_override)

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
        mc_raw = payload.get("model_config") or payload.get("llm_model_config") or {}
        mc = await self._enrich_finetuned_model_config(user_id, dict(mc_raw))
        ic = payload.get("interrupt_config")
        raw_skills = payload.get("skills")
        resolved_skills: list[str] | None = None
        if raw_skills is not None:
            processed_raw_skills = []
            for item in raw_skills:
                if isinstance(item, str):
                    processed_raw_skills.append(item)
                elif isinstance(item, dict):
                    sk_name = item.get("name")
                    from app.domain.value_objects import SkillParametersSchema

                    params = item.get("parameters_schema")
                    ps = (
                        SkillParametersSchema.model_validate(params)
                        if params
                        else SkillParametersSchema()
                    )

                    new_sk = await self._skill_repo.create(
                        user_id=user_id,
                        name=f"{sk_name} (Imported)" if sk_name else "Imported Skill",
                        description=item.get("description"),
                        skill_type=item.get("skill_type") or "code",
                        source_code=item.get("source_code") or "",
                        instructions=item.get("instructions"),
                        parameters_schema=ps,
                        permissions=item.get("permissions") or [],
                        is_public=False,
                    )
                    processed_raw_skills.append(str(new_sk.id))

            resolved_skills = await self._normalize_attached_skills(user_id, processed_raw_skills)
        ep = payload.get("execution_policy")
        pol_imp = parse_execution_policy(ep).to_dict() if ep else {}
        base = await self._repo.create(
            user_id=user_id,
            name=name,
            description=desc,
            graph_definition=gd,
            model_config=AgentModelConfig.model_validate(mc),
            skills=resolved_skills,
            execution_policy=pol_imp,
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
