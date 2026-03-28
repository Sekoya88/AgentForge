"""Structured diff between two agent version payloads (graph, model, skills)."""

from __future__ import annotations

from typing import Any


def _sorted_skill_ids(skills: list[Any]) -> list[str]:
    out: list[str] = []
    for s in skills:
        if isinstance(s, str):
            out.append(s)
        elif isinstance(s, dict) and s.get("name"):
            out.append(str(s["name"]))
    return sorted(set(out))


def diff_agent_versions(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    left_label: str = "from",
    right_label: str = "to",
) -> dict[str, Any]:
    """Compare graph_definition, model_config, skills, execution_policy."""
    lg = left.get("graph_definition") or {}
    rg = right.get("graph_definition") or {}
    lm = left.get("model_config") or {}
    rm = right.get("model_config") or {}
    ls = left.get("skills") or []
    rs = right.get("skills") or []
    lp = left.get("execution_policy") or {}
    rp = right.get("execution_policy") or {}

    entry_changed = lg.get("entry_point") != rg.get("entry_point")
    nodes_l = {n["id"]: n for n in (lg.get("nodes") or []) if isinstance(n, dict) and "id" in n}
    nodes_r = {n["id"]: n for n in (rg.get("nodes") or []) if isinstance(n, dict) and "id" in n}
    node_ids_l = set(nodes_l)
    node_ids_r = set(nodes_r)
    edges_l = lg.get("edges") or []
    edges_r = rg.get("edges") or []

    return {
        "labels": {left_label: left_label, right_label: right_label},
        "graph": {
            "entry_point_changed": entry_changed,
            "entry_point": {"left": lg.get("entry_point"), "right": rg.get("entry_point")},
            "nodes_added": sorted(node_ids_r - node_ids_l),
            "nodes_removed": sorted(node_ids_l - node_ids_r),
            "nodes_changed": sorted(
                nid for nid in node_ids_l & node_ids_r if nodes_l[nid] != nodes_r[nid]
            ),
            "edge_count": {"left": len(edges_l), "right": len(edges_r)},
            "edges_changed": edges_l != edges_r,
        },
        "model_config_changed": lm != rm,
        "skills": {
            "left": _sorted_skill_ids(ls),
            "right": _sorted_skill_ids(rs),
            "added": sorted(set(_sorted_skill_ids(rs)) - set(_sorted_skill_ids(ls))),
            "removed": sorted(set(_sorted_skill_ids(ls)) - set(_sorted_skill_ids(rs))),
        },
        "execution_policy_changed": lp != rp,
    }
