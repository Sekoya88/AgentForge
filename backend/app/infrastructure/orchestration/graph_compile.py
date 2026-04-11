"""Compile graph definition + edges into a LangGraph StateGraph (routing helpers)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.config import Settings
from app.domain.attached_skill_binding import AttachedSkillBinding
from app.domain.execution_policy import ExecutionPolicyValidated
from app.domain.ports.agent_orchestrator import KnowledgeSearchFn, SubagentResolver
from app.domain.ports.execution_events import ExecutionEventEmitter
from app.domain.ports.sandbox_runtime import SandboxRuntime
from app.infrastructure.orchestration.graph_state import (
    GraphState,
    last_ai_text,
    lg_node_name,
)


def definition_has_interrupt(definition: dict[str, Any]) -> bool:
    for n in definition.get("nodes") or []:
        if n.get("type") == "interrupt":
            return True
    return False


def default_definition() -> dict[str, Any]:
    return {
        "graph_schema_version": "1.0",
        "nodes": [{"id": "default", "type": "llm", "config": {}}],
        "edges": [],
        "entry_point": "default",
    }


def eval_single_condition(text: str, cond: str | None, cond_type: str) -> bool:
    """Evaluate a single (non-compound) edge condition against *text*."""
    if not text or not cond:
        return False

    if cond_type == "contains":
        return str(cond).lower() in text.lower()

    if cond_type == "not_contains":
        return str(cond).lower() not in text.lower()

    if cond_type == "equals":
        return str(cond).strip().lower() == text.strip().lower()

    if cond_type == "regex":
        try:
            return bool(re.search(str(cond), text, re.IGNORECASE))
        except re.error:
            return False

    if cond_type == "json_path":
        try:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(text[json_start:json_end])
                if "==" in str(cond):
                    path, expected = str(cond).split("==", 1)
                    keys = path.strip().split(".")
                    val = data
                    for k in keys:
                        val = val[k]
                    return str(val) == expected.strip()
                keys = str(cond).strip().split(".")
                val = data
                for k in keys:
                    val = val[k]
                return bool(val)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return False
        return False

    if cond_type in ("gt", "lt"):
        nums = re.findall(r"-?\d+(?:\.\d+)?", text)
        if nums:
            try:
                val = float(nums[0])
                threshold = float(str(cond))
                return val > threshold if cond_type == "gt" else val < threshold
            except ValueError:
                return False
        return False

    return False


def pick_next(state: GraphState, outs: list[dict[str, Any]]) -> str:
    last_ai = last_ai_text(state["messages"])
    default_dest: str | None = None

    for e in outs:
        cond = e.get("condition")
        cond_type = e.get("condition_type", "contains")
        dest = lg_node_name(e["to"])

        if cond_type == "always" or cond in (None, "", "always"):
            default_dest = dest
            continue

        if not last_ai or not cond:
            continue

        matched = False

        if cond_type in ("contains", "not_contains", "equals", "regex", "json_path", "gt", "lt"):
            matched = eval_single_condition(last_ai, cond, cond_type)

        elif cond_type == "and":
            try:
                sub_conditions = json.loads(str(cond)) if isinstance(cond, str) else cond
                matched = all(
                    eval_single_condition(
                        last_ai,
                        sc.get("condition"),
                        sc.get("condition_type", "contains"),
                    )
                    for sc in sub_conditions
                )
            except (json.JSONDecodeError, TypeError, AttributeError):
                matched = False

        elif cond_type == "or":
            try:
                sub_conditions = json.loads(str(cond)) if isinstance(cond, str) else cond
                matched = any(
                    eval_single_condition(
                        last_ai,
                        sc.get("condition"),
                        sc.get("condition_type", "contains"),
                    )
                    for sc in sub_conditions
                )
            except (json.JSONDecodeError, TypeError, AttributeError):
                matched = False

        if matched:
            return dest

    return default_dest if default_dest is not None else END


def attached_skills_by_name(
    bindings: Sequence[AttachedSkillBinding],
) -> dict[str, AttachedSkillBinding]:
    m: dict[str, AttachedSkillBinding] = {}
    for b in bindings:
        if b.name not in m:
            m[b.name] = b
    return m


def compile_state_graph(
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
    anthropic_key: str | None = None,
    google_oauth_access_token: str | None = None,
    google_oauth_scopes: frozenset[str] | None = None,
    execution_policy: ExecutionPolicyValidated | None = None,
    cost_meter: Any = None,
) -> StateGraph:
    """Build StateGraph from JSON definition.

    Imports `build_step` lazily to avoid import cycles.
    """
    from app.infrastructure.orchestration.node_builders import build_step as _build_step

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

    g = StateGraph(GraphState)
    for nid, spec in nodes_map.items():
        g.add_node(
            lg_node_name(nid),
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
                anthropic_key,
                google_oauth_access_token,
                google_oauth_scopes,
                execution_policy,
                cost_meter,
            ),
        )

    g.add_edge(START, lg_node_name(entry))

    for nid in nodes_map:
        outs = by_from.get(nid, [])
        src = lg_node_name(nid)
        if not outs:
            g.add_edge(src, END)
            continue
        if len(outs) == 1 and outs[0].get("condition") in (None, "", "always"):
            g.add_edge(src, lg_node_name(outs[0]["to"]))
            continue

        def make_router(edges_out: list[dict[str, Any]]):
            def route(state: GraphState) -> Any:
                return pick_next(state, edges_out)

            return route

        dests = {lg_node_name(e["to"]) for e in outs}
        dests.add(END)
        path_map: dict[Any, str] = {d: d for d in dests if d != END}
        path_map[END] = END
        g.add_conditional_edges(src, make_router(outs), path_map)

    return g
