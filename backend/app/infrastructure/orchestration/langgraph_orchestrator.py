import base64
import json
import re
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, message_to_dict
from langfuse import observe
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from app.config import Settings, get_settings
from app.domain.attached_skill_binding import AttachedSkillBinding
from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.orchestration_result import OrchestrationResult
from app.domain.ports.agent_orchestrator import (
    AgentOrchestrator,
    KnowledgeSearchFn,
    SubagentResolver,
)
from app.domain.ports.execution_events import ExecutionEventEmitter, NullExecutionEmitter
from app.domain.ports.sandbox_runtime import SandboxRuntime
from app.domain.value_objects import AgentModelConfig, MessageDict
from app.infrastructure.orchestration.checkpoint_registry import get_checkpointer
from app.infrastructure.orchestration.llm_invoke import (
    _get_observability_callbacks,
    invoke_chat_llm,
)
from app.infrastructure.sandbox.subprocess_sandbox import SubprocessSandboxRuntime

if TYPE_CHECKING:
    from app.domain.entities.agent import Agent


def _langfuse_update_current_span(**kwargs: Any) -> None:
    """Update active Langfuse span; no-op if client unavailable or tracing disabled."""
    try:
        from langfuse import get_client

        get_client().update_current_span(**kwargs)
    except Exception:
        pass


class _State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _dicts_to_messages(items: list[MessageDict]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in items:
        role = m.role
        content = m.content
        if role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def _messages_to_dicts(msgs: list[BaseMessage]) -> list[MessageDict]:
    res = []
    for m in msgs:
        d = message_to_dict(m)
        content = d.get("data", {}).get("content", "")
        role = "assistant" if d.get("type") == "ai" else "user"
        res.append(MessageDict(role=role, content=str(content)))
    return res


def _message_tail_preview(msgs: list[BaseMessage], limit: int = 240) -> str:
    if not msgs:
        return ""
    last = msgs[-1]
    c = str(getattr(last, "content", "") or "")
    return c if len(c) <= limit else c[: limit - 3] + "..."


def _last_ai_text(msgs: list[BaseMessage]) -> str:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            return str(m.content or "")
    return ""


def _lg_node_name(node_id: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in node_id)
    return f"g_{safe}"


_MAX_SUBAGENT_DEPTH = 5


def _definition_has_interrupt(definition: dict[str, Any]) -> bool:
    for n in definition.get("nodes") or []:
        if n.get("type") == "interrupt":
            return True
    return False


def _default_definition() -> dict[str, Any]:
    return {
        "nodes": [{"id": "default", "type": "llm", "config": {}}],
        "edges": [],
        "entry_point": "default",
    }


def _pick_next(
    state: _State,
    outs: list[dict[str, Any]],
) -> str:
    last_ai = _last_ai_text(state["messages"])
    default_dest: str | None = None

    for e in outs:
        cond = e.get("condition")
        cond_type = e.get("condition_type", "contains")
        dest = _lg_node_name(e["to"])

        # "always" or empty condition -> use as default fallback
        if cond_type == "always" or cond in (None, "", "always"):
            default_dest = dest
            continue

        if not last_ai or not cond:
            continue

        matched = False
        if cond_type == "contains":
            matched = str(cond).lower() in last_ai.lower()
        elif cond_type == "regex":
            try:
                matched = bool(re.search(str(cond), last_ai, re.IGNORECASE))
            except re.error:
                matched = False
        elif cond_type == "json_path":
            try:
                json_start = last_ai.find("{")
                json_end = last_ai.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(last_ai[json_start:json_end])
                    if "==" in str(cond):
                        path, expected = str(cond).split("==", 1)
                        keys = path.strip().split(".")
                        val = data
                        for k in keys:
                            val = val[k]
                        matched = str(val) == expected.strip()
                    else:
                        keys = str(cond).strip().split(".")
                        val = data
                        for k in keys:
                            val = val[k]
                        matched = bool(val)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                matched = False

        if matched:
            return dest

    return default_dest if default_dest is not None else END


def _merge_node_model_config(
    agent_model_config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(agent_model_config)
    if node_config.get("model") is not None:
        merged["model"] = node_config["model"]
    if node_config.get("temperature") is not None:
        merged["temperature"] = node_config["temperature"]
    return merged


def _attached_skills_by_name(
    bindings: Sequence[AttachedSkillBinding],
) -> dict[str, AttachedSkillBinding]:
    m: dict[str, AttachedSkillBinding] = {}
    for b in bindings:
        if b.name not in m:
            m[b.name] = b
    return m


async def _run_attached_skill_code(
    sandbox: SandboxRuntime,
    source_code: str,
    input_text: str,
    *,
    timeout_sec: float,
) -> str:
    """Execute skill `run(str) -> str` in an isolated subprocess (see SandboxRuntime)."""
    src_b64 = base64.b64encode(source_code.encode()).decode("ascii")
    inp_b64 = base64.b64encode(input_text.encode()).decode("ascii")
    _mode = "exe" + "c"
    driver = (
        "import base64,sys,builtins\n"
        f'_SRC_B64="{src_b64}"\n'
        f'_INP_B64="{inp_b64}"\n'
        "src=base64.b64decode(_SRC_B64).decode()\n"
        "ns={}\n"
        f"getattr(builtins, '{_mode}')(compile(src, '<skill>', '{_mode}'), ns, ns)\n"
        "run=ns.get('run')\n"
        "if run is None:\n"
        "    sys.stderr.write('Skill has no run()\\n')\n"
        "    sys.exit(2)\n"
        'inp=base64.b64decode(_INP_B64).decode(errors="replace")\n'
        "out=run(inp)\n"
        "sys.stdout.write(str(out))\n"
    )
    exit_code, out, err = await sandbox.run_python(driver, timeout_sec)
    if exit_code != 0:
        tail = (err or out or "").strip()
        return f"[skill_error code={exit_code}] {tail}"
    return out


@observe(as_type="tool", name="tool_dispatch")
async def _observed_tool_dispatch(
    tool_name: str,
    arg: str,
    handler,
) -> str:
    """Run tool handler with Langfuse span. `handler` is an async callable(arg) -> str."""
    _langfuse_update_current_span(
        name=f"tool:{tool_name}",
        input={"tool_name": tool_name, "arg": arg[:500]},
    )
    result = await handler(arg)
    _langfuse_update_current_span(output=str(result)[:500])
    return result


@observe(as_type="retriever", name="knowledge_retrieve")
async def _observed_retrieve_dispatch(arg: str, handler) -> str:
    _langfuse_update_current_span(
        input={"arg": arg[:500]},
    )
    result = await handler(arg)
    _langfuse_update_current_span(output=str(result)[:500])
    return result


def _build_step(
    node_id: str,
    spec: dict[str, Any],
    bus: ExecutionEventEmitter,
    agent_model_config: dict[str, Any],
    settings: Settings,
    attached_skills: dict[str, AttachedSkillBinding],
    sandbox: SandboxRuntime,
    skill_timeout_sec: float,
    knowledge_search: KnowledgeSearchFn | None,
    openai_key: str | None,
    google_key: str | None,
    subagent_resolver: SubagentResolver | None = None,
    subagent_depth: int = 0,
):
    ntype = spec.get("type", "llm")

    async def step(state: _State):
        t0 = time.perf_counter()
        await bus.emit(
            "agent_start",
            {
                "agent_name": node_id,
                "node_type": ntype,
                "input_preview": _message_tail_preview(state["messages"]),
            },
        )
        if ntype == "interrupt":
            cfg = spec.get("config") or {}
            payload = {
                "node_id": node_id,
                "allowed_decisions": cfg.get("allowed_decisions", ["approve", "reject"]),
            }
            await bus.emit("interrupt", payload)
            answer = interrupt(payload)
            msg = AIMessage(content=f"[human_decision:{answer}]")
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": str(msg.content)[:500],
                },
            )
            return {"messages": [msg]}
        if ntype == "conditional":
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": "(router)",
                },
            )
            return {}
        if ntype == "tool":
            cfg = spec.get("config") or {}
            tool_name = cfg.get("tool_name", "tool")

            last_msg = next(
                (
                    m
                    for m in reversed(state["messages"])
                    if isinstance(m, (HumanMessage, AIMessage))
                ),
                None,
            )
            arg = str(last_msg.content) if last_msg else ""

            await bus.emit("tool_call", {"tool_name": tool_name, "args": {"input": arg}})

            skill_binding = attached_skills.get(tool_name)
            # Built-ins first, then registry skills (tool_name must match skill.name).
            if tool_name == "fetch":
                import urllib.request

                async def _fetch_handler(input_arg: str) -> str:
                    try:
                        req = urllib.request.Request(
                            input_arg, headers={"User-Agent": "AgentForge/1.0"}
                        )
                        with urllib.request.urlopen(req, timeout=5) as response:
                            return response.read().decode("utf-8")[:500]
                    except Exception as e:
                        return f"Fetch Error: {e}"

                handler = _fetch_handler

            elif tool_name == "echo":

                async def _echo_handler(input_arg: str) -> str:
                    return f"Echo: {input_arg}"

                handler = _echo_handler

            elif tool_name == "retrieve":
                top_k = int(cfg.get("top_k") or 5)

                async def _retrieve_handler(input_arg: str) -> str:
                    if knowledge_search is not None:
                        return await knowledge_search(input_arg, top_k)
                    return "[retrieve] Knowledge search is not available for this execution."

                handler = _retrieve_handler

            elif skill_binding is not None:
                if skill_binding.skill_type == "instruction":

                    async def _instruction_handler(input_arg: str) -> str:  # noqa: F811
                        return skill_binding.instructions or "(no instructions)"

                    handler = _instruction_handler
                else:
                    if not skill_binding.security_validated:
                        await bus.emit(
                            "skill_notice",
                            {
                                "tool_name": tool_name,
                                "message": "Skill is not marked security_validated",
                            },
                        )

                    async def _skill_handler(input_arg: str) -> str:  # noqa: F811
                        return await _run_attached_skill_code(
                            sandbox,
                            skill_binding.source_code,
                            input_arg,
                            timeout_sec=skill_timeout_sec,
                        )

                    handler = _skill_handler
            else:

                async def _stub_handler(input_arg: str) -> str:  # noqa: F811
                    return f"[tool:{tool_name}] executed with input '{input_arg}' (stub)."

                handler = _stub_handler

            if tool_name == "retrieve":
                res = await _observed_retrieve_dispatch(arg=arg, handler=handler)
            else:
                res = await _observed_tool_dispatch(tool_name=tool_name, arg=arg, handler=handler)

            msg = AIMessage(content=f"Tool '{tool_name}' result: {res}")
            await bus.emit("tool_result", {"tool_name": tool_name, "result": msg.content})
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": str(msg.content)[:500],
                },
            )
            return {"messages": [msg]}
        if ntype == "subagent":
            cfg = spec.get("config") or {}
            subagent_id_str = cfg.get("subagent_id")
            label = cfg.get("subagent_name") or node_id

            if subagent_depth >= _MAX_SUBAGENT_DEPTH:
                msg = AIMessage(
                    content=(
                        f"[subagent:{label}] Error: maximum subagent recursion depth"
                        f" ({_MAX_SUBAGENT_DEPTH}) exceeded."
                    )
                )
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}

            if not subagent_id_str or subagent_resolver is None:
                msg = AIMessage(
                    content=(
                        f"[subagent:{label}] Error: subagent_id not configured"
                        " or resolver unavailable."
                    )
                )
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}

            try:
                target_agent: Agent = await subagent_resolver(UUID(subagent_id_str))
            except Exception as e:
                msg = AIMessage(content=f"[subagent:{label}] Error resolving agent: {e}")
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}

            # Check if subagent graph contains interrupt nodes — not supported in nested execution
            subagent_def = (
                target_agent.graph_definition.to_dict() if target_agent.graph_definition else {}
            )
            if _definition_has_interrupt(subagent_def):
                msg = AIMessage(
                    content=(
                        f"[subagent:{label}] Error: subagent graphs with interrupt nodes"
                        " are not supported in nested execution."
                    )
                )
                dur = int((time.perf_counter() - t0) * 1000)
                await bus.emit(
                    "agent_end",
                    {
                        "agent_name": node_id,
                        "duration_ms": dur,
                        "output_preview": str(msg.content)[:500],
                    },
                )
                return {"messages": [msg]}

            # Delegate to sub-orchestrator (new instance, same settings/sandbox)
            # LangGraphAgentOrchestrator is defined in this same module; no import needed
            sub_orchestrator = LangGraphAgentOrchestrator(
                settings=settings,
                sandbox=sandbox,
                skill_timeout_sec=skill_timeout_sec,
            )
            input_msgs = [
                MessageDict(
                    role="user" if isinstance(m, HumanMessage) else "assistant",
                    content=str(m.content),
                )
                for m in state["messages"]
            ]
            try:
                sub_result = await sub_orchestrator.run(
                    agent_id=target_agent.id,
                    graph_definition=target_agent.graph_definition,
                    model_config=target_agent.model_config,
                    input_messages=input_msgs,
                    emitter=bus,
                    agent_label=target_agent.name,
                    openai_key=openai_key,
                    google_key=google_key,
                    subagent_depth=subagent_depth + 1,
                )
                last_out = (
                    sub_result.output_messages[-1].content
                    if sub_result.output_messages
                    else "(no output)"
                )
                msg = AIMessage(content=f"[subagent:{label}] {last_out}")
            except Exception as e:
                msg = AIMessage(content=f"[subagent:{label}] Execution error: {e}")

            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": str(msg.content)[:500],
                },
            )
            return {"messages": [msg]}
        cfg = spec.get("config") or {}
        prompt = str(cfg.get("prompt") or "")
        # Inject instruction-type skills into the LLM system prompt
        instruction_parts: list[str] = []
        for sk in attached_skills.values():
            if sk.skill_type == "instruction" and sk.instructions:
                instruction_parts.append(f"## Skill: {sk.name}\n{sk.instructions}")
        if instruction_parts:
            skills_block = "\n\n---\n\n".join(instruction_parts)
            prompt = (
                f"{prompt}\n\n# Attached Skills\n\n{skills_block}"
                if prompt
                else f"# Attached Skills\n\n{skills_block}"
            )
        node_mc = _merge_node_model_config(agent_model_config, cfg)
        try:
            text = await invoke_chat_llm(
                state["messages"],
                system_prompt=prompt,
                model_config=node_mc,
                openai_api_key=openai_key or settings.openai_api_key,
                google_api_key=google_key or settings.google_api_key,
            )
        except Exception as e:
            dur = int((time.perf_counter() - t0) * 1000)
            await bus.emit(
                "agent_end",
                {
                    "agent_name": node_id,
                    "duration_ms": dur,
                    "output_preview": f"(error) {e!s}"[:500],
                },
            )
            raise
        msg = AIMessage(content=text)
        dur = int((time.perf_counter() - t0) * 1000)
        await bus.emit(
            "agent_end",
            {
                "agent_name": node_id,
                "duration_ms": dur,
                "output_preview": str(msg.content)[:500],
            },
        )
        return {"messages": [msg]}

    return step


def _compile_state_graph(
    definition: dict[str, Any],
    bus: ExecutionEventEmitter,
    agent_model_config: dict[str, Any],
    settings: Settings,
    attached_skills: dict[str, AttachedSkillBinding],
    sandbox: SandboxRuntime,
    skill_timeout_sec: float,
    knowledge_search: KnowledgeSearchFn | None,
    openai_key: str | None = None,
    google_key: str | None = None,
    subagent_resolver: SubagentResolver | None = None,
    subagent_depth: int = 0,
) -> StateGraph:
    nodes_map: dict[str, dict[str, Any]] = {
        n["id"]: n for n in (definition.get("nodes") or []) if "id" in n
    }
    raw_edges = definition.get("edges") or []
    by_from: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in raw_edges:
        if "from" in e and "to" in e:
            by_from[e["from"]].append(e)
    entry = definition.get("entry_point")
    if not entry or entry not in nodes_map:
        entry = next(iter(nodes_map))

    g = StateGraph(_State)
    for nid, spec in nodes_map.items():
        g.add_node(
            _lg_node_name(nid),
            _build_step(
                nid,
                spec,
                bus,
                agent_model_config,
                settings,
                attached_skills,
                sandbox,
                skill_timeout_sec,
                knowledge_search,
                openai_key,
                google_key,
                subagent_resolver,
                subagent_depth,
            ),
        )

    g.add_edge(START, _lg_node_name(entry))

    for nid in nodes_map:
        outs = by_from.get(nid, [])
        src = _lg_node_name(nid)
        if not outs:
            g.add_edge(src, END)
            continue
        if len(outs) == 1 and outs[0].get("condition") in (None, "", "always"):
            g.add_edge(src, _lg_node_name(outs[0]["to"]))
            continue

        def make_router(edges_out: list[dict[str, Any]]):
            def route(state: _State) -> Any:
                return _pick_next(state, edges_out)

            return route

        dests = {_lg_node_name(e["to"]) for e in outs}
        dests.add(END)
        path_map: dict[Any, str] = {d: d for d in dests if d != END}
        path_map[END] = END
        g.add_conditional_edges(src, make_router(outs), path_map)

    return g


def _process_invoke_result(
    result: dict[str, Any],
    *,
    duration_ms: int,
    bus: ExecutionEventEmitter,
    agent_id: UUID,
    agent_label: str | None,
    execution_id: UUID | None,
    had_checkpoint: bool,
) -> OrchestrationResult:
    intrs = result.get("__interrupt__") or []
    msgs = result.get("messages") or []
    out_dicts = _messages_to_dicts(msgs)
    if intrs:
        first = intrs[0]
        val = getattr(first, "value", first)
        iid = getattr(first, "id", None)
        payload: dict[str, Any] = {"interrupt_id": str(iid) if iid else None}
        if isinstance(val, dict):
            payload.update(val)
        else:
            payload["value"] = val
        return OrchestrationResult(out_dicts, None, duration_ms, payload)
    return OrchestrationResult(out_dicts, None, duration_ms, None)


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
        subagent_resolver: SubagentResolver | None = None,
        subagent_depth: int = 0,
    ) -> OrchestrationResult:
        _langfuse_update_current_span(
            input={"agent_id": str(agent_id), "agent_name": agent_label},
            metadata={"model_config": model_config.to_dict()},
        )
        bus: ExecutionEventEmitter = emitter or NullExecutionEmitter()
        definition = graph_definition.to_dict() if graph_definition else {"nodes": [], "edges": []}
        if not definition.get("nodes"):
            definition = _default_definition()

        need_cp = _definition_has_interrupt(definition)
        if need_cp and execution_id is None:
            raise ValueError("execution_id is required when the graph contains interrupt nodes")

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
        )
        t0 = time.perf_counter()

        callbacks = _get_observability_callbacks(self._settings)
        cfg: dict[str, Any] = {"callbacks": callbacks}

        if need_cp:
            async with get_checkpointer() as checkpointer:
                compiled = g.compile(checkpointer=checkpointer)
                cfg["configurable"] = {"thread_id": str(execution_id)}
                result = await compiled.ainvoke(
                    {"messages": _dicts_to_messages(input_messages)},
                    cfg,
                )
        else:
            compiled = g.compile()
            result = await compiled.ainvoke({"messages": _dicts_to_messages(input_messages)}, cfg)

        duration_ms = int((time.perf_counter() - t0) * 1000)

        orch = _process_invoke_result(
            result,
            duration_ms=duration_ms,
            bus=bus,
            agent_id=agent_id,
            agent_label=agent_label,
            execution_id=execution_id,
            had_checkpoint=need_cp,
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
        subagent_resolver: SubagentResolver | None = None,
    ) -> OrchestrationResult:
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
        )

        callbacks = _get_observability_callbacks(self._settings)
        cfg: dict[str, Any] = {
            "configurable": {"thread_id": str(execution_id)},
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
        )
        return orch
