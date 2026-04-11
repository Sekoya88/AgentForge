import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from uuid import UUID

from langfuse import observe
from langgraph.types import Command

from app.config import Settings, get_settings
from app.domain.attached_skill_binding import AttachedSkillBinding
from app.domain.execution_policy import ExecutionPolicyValidated, parse_execution_policy
from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.orchestration_result import OrchestrationResult
from app.domain.ports.agent_orchestrator import (
    AgentOrchestrator,
    SubagentResolver,
)
from app.domain.ports.execution_events import ExecutionEventEmitter, NullExecutionEmitter
from app.domain.ports.sandbox_runtime import SandboxRuntime
from app.domain.value_objects import AgentModelConfig, MessageDict
from app.infrastructure.orchestration.checkpoint_registry import get_checkpointer
from app.infrastructure.orchestration.cost_meter import ExecutionCostMeter
from app.infrastructure.orchestration.graph_compile import (
    attached_skills_by_name as _attached_skills_by_name,
)
from app.infrastructure.orchestration.graph_compile import (
    compile_state_graph as _compile_state_graph,
)
from app.infrastructure.orchestration.graph_compile import (
    default_definition as _default_definition,
)
from app.infrastructure.orchestration.graph_compile import (
    definition_has_interrupt as _definition_has_interrupt,
)
from app.infrastructure.orchestration.graph_state import (
    dicts_to_messages as _dicts_to_messages,
)
from app.infrastructure.orchestration.graph_state import (
    messages_to_dicts as _messages_to_dicts,
)
from app.infrastructure.orchestration.llm_invoke import _get_observability_callbacks
from app.infrastructure.orchestration.node_builders import (  # noqa: F401
    _build_asr_provider,
    _build_tts_provider,
    _merge_node_model_config,
    _observed_tool_dispatch,
    _run_asr_node,
    _run_tts_node,
)
from app.infrastructure.sandbox.subprocess_sandbox import SubprocessSandboxRuntime


def _langfuse_update_current_span(**kwargs: Any) -> None:
    """Update active Langfuse span; no-op if client unavailable or tracing disabled."""
    try:
        from langfuse import get_client

        get_client().update_current_span(**kwargs)
    except Exception:
        pass


def _langfuse_enrich_agent_trace(
    *,
    user_id: UUID | None = None,
    session_id: str | None = None,
    execution_id: UUID | None = None,
) -> None:
    """Attach user/session/execution to the current trace for Langfuse filtering."""
    meta: dict[str, Any] = {}
    if user_id is not None:
        meta["user_id"] = str(user_id)
    if session_id:
        meta["session_id"] = session_id
    if execution_id is not None:
        meta["execution_id"] = str(execution_id)
    if meta:
        _langfuse_update_current_span(metadata=meta)


def _process_invoke_result(
    result: dict[str, Any],
    *,
    duration_ms: int,
    bus: ExecutionEventEmitter,
    agent_id: UUID,
    agent_label: str | None,
    execution_id: UUID | None,
    had_checkpoint: bool,
    cost_meter: ExecutionCostMeter | None = None,
) -> OrchestrationResult:
    intrs = result.get("__interrupt__") or []
    msgs = result.get("messages") or []
    out_dicts = _messages_to_dicts(msgs)
    token_usage = cost_meter.get_token_usage_dict() if cost_meter else None
    audio_out = result.get("audio_b64")
    out_b64 = audio_out if isinstance(audio_out, str) else None

    if intrs:
        first = intrs[0]
        val = getattr(first, "value", first)
        iid = getattr(first, "id", None)
        payload: dict[str, Any] = {"interrupt_id": str(iid) if iid else None}
        if isinstance(val, dict):
            payload.update(val)
        else:
            payload["value"] = val
        return OrchestrationResult(
            out_dicts, token_usage, duration_ms, payload, output_audio_b64=out_b64
        )
    return OrchestrationResult(out_dicts, token_usage, duration_ms, None, output_audio_b64=out_b64)


class LangGraphAgentOrchestrator(AgentOrchestrator):
    def __init__(
        self,
        settings: Settings | None = None,
        sandbox: SandboxRuntime | None = None,
        skill_timeout_sec: float = 15.0,
    ) -> None:
        self._settings = settings or get_settings()
        self._sandbox = sandbox or SubprocessSandboxRuntime()
        self._skill_timeout_sec = skill_timeout_sec

    @observe(as_type="agent", name="agent_run")
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
        attached_skills: Sequence[AttachedSkillBinding] | None = None,
        knowledge_search: Callable[[str, int], Awaitable[str]] | None = None,
        openai_key: str | None = None,
        google_key: str | None = None,
        anthropic_key: str | None = None,
        subagent_resolver: SubagentResolver | None = None,
        subagent_depth: int = 0,
        google_oauth_access_token: str | None = None,
        google_oauth_scopes: frozenset[str] | None = None,
        execution_policy: dict[str, Any] | ExecutionPolicyValidated | None = None,
        graph_extra: dict[str, Any] | None = None,
        langfuse_user_id: UUID | None = None,
        langfuse_session_id: str | None = None,
    ) -> OrchestrationResult:
        lf_meta: dict[str, Any] = {"model_config": model_config.to_dict()}
        if langfuse_user_id is not None:
            lf_meta["user_id"] = str(langfuse_user_id)
        if langfuse_session_id:
            lf_meta["session_id"] = langfuse_session_id
        if execution_id is not None:
            lf_meta["execution_id"] = str(execution_id)
        _langfuse_update_current_span(
            input={"agent_id": str(agent_id), "agent_name": agent_label},
            metadata=lf_meta,
        )
        bus: ExecutionEventEmitter = emitter or NullExecutionEmitter()
        definition = graph_definition.to_dict() if graph_definition else {"nodes": [], "edges": []}
        if not definition.get("nodes"):
            definition = _default_definition()

        need_cp = _definition_has_interrupt(definition)
        if need_cp and execution_id is None:
            raise ValueError("execution_id is required when the graph contains interrupt nodes")

        parsed_policy: ExecutionPolicyValidated | None = None
        if isinstance(execution_policy, ExecutionPolicyValidated):
            parsed_policy = execution_policy
        elif isinstance(execution_policy, dict):
            parsed_policy = parse_execution_policy(execution_policy)

        max_cost_usd = parsed_policy.max_cost_usd if parsed_policy else None
        cost_meter = ExecutionCostMeter(max_cost_usd=max_cost_usd)

        skill_map = _attached_skills_by_name(attached_skills or ())
        g = _compile_state_graph(
            definition,
            bus,
            model_config.to_dict(),
            self._settings,
            skill_map,
            self._sandbox,
            self._skill_timeout_sec,
            knowledge_search,
            openai_key,
            google_key,
            subagent_resolver,
            subagent_depth,
            anthropic_key,
            google_oauth_access_token,
            google_oauth_scopes,
            parsed_policy,
            cost_meter,
        )
        t0 = time.perf_counter()

        callbacks = _get_observability_callbacks(self._settings)
        cfg: dict[str, Any] = {"callbacks": callbacks}

        initial_state: dict[str, Any] = {
            "messages": _dicts_to_messages(input_messages),
            "audio_b64": None,
        }
        if graph_extra and graph_extra.get("audio_b64") is not None:
            initial_state["audio_b64"] = graph_extra["audio_b64"]
        for inj in ("__memory_store__", "__user_id__", "__agent_id__"):
            if graph_extra and graph_extra.get(inj) is not None:
                if need_cp and inj == "__memory_store__":
                    continue
                initial_state[inj] = graph_extra[inj]

        if need_cp:
            async with get_checkpointer() as checkpointer:
                compiled = g.compile(checkpointer=checkpointer)
                cconf: dict[str, Any] = {"thread_id": str(execution_id)}
                if graph_extra and graph_extra.get("__memory_store__") is not None:
                    cconf["__memory_store__"] = graph_extra["__memory_store__"]
                cfg["configurable"] = cconf
                result = await compiled.ainvoke(initial_state, cfg)
        else:
            compiled = g.compile()
            result = await compiled.ainvoke(initial_state, cfg)

        duration_ms = int((time.perf_counter() - t0) * 1000)

        orch = _process_invoke_result(
            result,
            duration_ms=duration_ms,
            bus=bus,
            agent_id=agent_id,
            agent_label=agent_label,
            execution_id=execution_id,
            had_checkpoint=need_cp,
            cost_meter=cost_meter,
        )
        return orch

    @observe(as_type="agent", name="agent_resume")
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
        attached_skills: Sequence[AttachedSkillBinding] | None = None,
        knowledge_search: Callable[[str, int], Awaitable[str]] | None = None,
        openai_key: str | None = None,
        google_key: str | None = None,
        anthropic_key: str | None = None,
        subagent_resolver: SubagentResolver | None = None,
        google_oauth_access_token: str | None = None,
        google_oauth_scopes: frozenset[str] | None = None,
        execution_policy: dict[str, Any] | ExecutionPolicyValidated | None = None,
        langfuse_user_id: UUID | None = None,
        langfuse_session_id: str | None = None,
        graph_extra: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        _langfuse_enrich_agent_trace(
            user_id=langfuse_user_id,
            session_id=langfuse_session_id,
            execution_id=execution_id,
        )
        parsed_resume_policy: ExecutionPolicyValidated | None = None
        if isinstance(execution_policy, ExecutionPolicyValidated):
            parsed_resume_policy = execution_policy
        elif isinstance(execution_policy, dict):
            parsed_resume_policy = parse_execution_policy(execution_policy)

        max_cost_resume = parsed_resume_policy.max_cost_usd if parsed_resume_policy else None
        cost_meter = ExecutionCostMeter(max_cost_usd=max_cost_resume)

        bus: ExecutionEventEmitter = emitter or NullExecutionEmitter()
        definition = (
            graph_definition.to_dict()
            if graph_definition and graph_definition.nodes
            else _default_definition()
        )
        skill_map = _attached_skills_by_name(attached_skills or ())
        g = _compile_state_graph(
            definition,
            bus,
            model_config.to_dict(),
            self._settings,
            skill_map,
            self._sandbox,
            self._skill_timeout_sec,
            knowledge_search,
            openai_key,
            google_key,
            subagent_resolver,
            0,
            anthropic_key,
            google_oauth_access_token,
            google_oauth_scopes,
            parsed_resume_policy,
            cost_meter,
        )

        callbacks = _get_observability_callbacks(self._settings)
        cconf_resume: dict[str, Any] = {"thread_id": str(execution_id)}
        if graph_extra and graph_extra.get("__memory_store__") is not None:
            cconf_resume["__memory_store__"] = graph_extra["__memory_store__"]
        cfg: dict[str, Any] = {
            "configurable": cconf_resume,
            "callbacks": callbacks,
        }

        async with get_checkpointer() as checkpointer:
            compiled = g.compile(checkpointer=checkpointer)
            snapshot = await checkpointer.aget_tuple(cfg)
            if snapshot is None:
                raise ValueError("No checkpoint for this execution; cannot resume")
            t0 = time.perf_counter()
            result = await compiled.ainvoke(Command(resume=resume_value), cfg)

        duration_ms = int((time.perf_counter() - t0) * 1000)
        orch = _process_invoke_result(
            result,
            duration_ms=duration_ms,
            bus=bus,
            agent_id=agent_id,
            agent_label=agent_label,
            execution_id=execution_id,
            had_checkpoint=True,
            cost_meter=cost_meter,
        )
        return orch
