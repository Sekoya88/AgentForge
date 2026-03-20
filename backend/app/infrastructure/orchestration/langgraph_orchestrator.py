import time
from collections import defaultdict
from typing import Annotated, Any
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, message_to_dict
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from app.config import Settings, get_settings
from app.domain.orchestration_result import OrchestrationResult
from app.domain.ports.agent_orchestrator import AgentOrchestrator
from app.domain.ports.execution_events import ExecutionEventEmitter, NullExecutionEmitter
from app.infrastructure.orchestration.checkpoint_registry import get_saver, pop_saver, put_saver
from app.infrastructure.orchestration.llm_invoke import invoke_chat_llm


class _State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _dicts_to_messages(items: list[dict[str, Any]]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in items:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "assistant":
            out.append(AIMessage(content=str(content)))
        else:
            out.append(HumanMessage(content=str(content)))
    return out


def _messages_to_dicts(msgs: list[BaseMessage]) -> list[dict[str, Any]]:
    return [message_to_dict(m) for m in msgs]


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
    last_ai = _last_ai_text(state["messages"]).lower()
    default_dest: str | None = None
    for e in outs:
        cond = e.get("condition")
        dest = _lg_node_name(e["to"])
        if cond in (None, "", "always"):
            default_dest = dest
            continue
        if last_ai and str(cond).lower() in last_ai:
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


def _build_step(
    node_id: str,
    spec: dict[str, Any],
    bus: ExecutionEventEmitter,
    agent_model_config: dict[str, Any],
    settings: Settings,
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
            tool_name = (spec.get("config") or {}).get("tool_name", "tool")
            await bus.emit("tool_call", {"tool_name": tool_name, "args": {}})
            msg = AIMessage(content=f"[tool:{tool_name}] executed (stub).")
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
            label = cfg.get("subagent_name") or node_id
            prompt = cfg.get("system_prompt") or ""
            last_human = next(
                (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
                None,
            )
            user_text = str(last_human.content) if last_human else ""
            body = f"{prompt}\n\n{user_text}".strip() if prompt else user_text
            if not body:
                body = "(empty)"
            msg = AIMessage(content=f"[subagent:{label}] Echo: {body}")
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
        node_mc = _merge_node_model_config(agent_model_config, cfg)
        try:
            text = await invoke_chat_llm(
                state["messages"],
                system_prompt=prompt,
                model_config=node_mc,
                openai_api_key=settings.openai_api_key,
                google_api_key=settings.google_api_key,
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
            _build_step(nid, spec, bus, agent_model_config, settings),
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
    if had_checkpoint and execution_id:
        pop_saver(execution_id)
    return OrchestrationResult(out_dicts, None, duration_ms, None)


class LangGraphAgentOrchestrator(AgentOrchestrator):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def run(
        self,
        agent_id: UUID,
        graph_definition: dict[str, Any],
        model_config: dict[str, Any],
        input_messages: list[dict[str, Any]],
        *,
        emitter: ExecutionEventEmitter | None = None,
        agent_label: str | None = None,
        execution_id: UUID | None = None,
    ) -> OrchestrationResult:
        bus: ExecutionEventEmitter = emitter or NullExecutionEmitter()
        definition = graph_definition if graph_definition else {"nodes": [], "edges": []}
        if not definition.get("nodes"):
            definition = _default_definition()

        need_cp = _definition_has_interrupt(definition)
        if need_cp and execution_id is None:
            raise ValueError("execution_id is required when the graph contains interrupt nodes")

        g = _compile_state_graph(definition, bus, model_config, self._settings)
        checkpointer = InMemorySaver() if need_cp else None
        if checkpointer and execution_id:
            put_saver(execution_id, checkpointer)
        compiled = g.compile(checkpointer=checkpointer) if checkpointer else g.compile()
        cfg: dict[str, Any] | None = (
            {"configurable": {"thread_id": str(execution_id)}} if checkpointer else None
        )

        t0 = time.perf_counter()
        if cfg:
            result = await compiled.ainvoke(
                {"messages": _dicts_to_messages(input_messages)},
                cfg,
            )
        else:
            result = await compiled.ainvoke({"messages": _dicts_to_messages(input_messages)})
        duration_ms = int((time.perf_counter() - t0) * 1000)

        orch = _process_invoke_result(
            result,
            duration_ms=duration_ms,
            bus=bus,
            agent_id=agent_id,
            agent_label=agent_label,
            execution_id=execution_id,
            had_checkpoint=bool(checkpointer),
        )
        if orch.interrupt_payload is None:
            await bus.emit(
                "complete",
                {
                    "agent_id": str(agent_id),
                    "agent_name": agent_label,
                    "total_duration_ms": duration_ms,
                    "message_count": len(orch.output_messages),
                },
            )
        return orch

    async def resume(
        self,
        execution_id: UUID,
        agent_id: UUID,
        graph_definition: dict[str, Any],
        model_config: dict[str, Any],
        resume_value: Any,
        *,
        emitter: ExecutionEventEmitter | None = None,
        agent_label: str | None = None,
    ) -> OrchestrationResult:
        saver = get_saver(execution_id)
        if saver is None:
            raise ValueError("No checkpoint for this execution; cannot resume")
        bus: ExecutionEventEmitter = emitter or NullExecutionEmitter()
        definition = graph_definition if graph_definition.get("nodes") else _default_definition()
        g = _compile_state_graph(definition, bus, model_config, self._settings)
        compiled = g.compile(checkpointer=saver)
        cfg = {"configurable": {"thread_id": str(execution_id)}}
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
        if orch.interrupt_payload is None:
            await bus.emit(
                "complete",
                {
                    "agent_id": str(agent_id),
                    "agent_name": agent_label,
                    "total_duration_ms": duration_ms,
                    "message_count": len(orch.output_messages),
                },
            )
        return orch
