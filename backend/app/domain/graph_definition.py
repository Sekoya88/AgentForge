"""Validate agent graph_definition JSON (builder + orchestrator contract)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NodeType = Literal["llm", "tool", "subagent", "conditional", "interrupt"]


class GraphNode(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    type: str = Field(
        default="llm",
        max_length=64,
        description="Built-in or plugin-registered node type.",
    )
    config: dict[str, Any] = Field(default_factory=dict)


ConditionType = Literal["contains", "regex", "json_path", "always"]


class GraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from", min_length=1, max_length=128)
    to: str = Field(min_length=1, max_length=128)
    condition: str | None = None
    condition_type: ConditionType = "contains"


class GraphDefinitionValidated(BaseModel):
    """§6.1 shape: nodes, edges, entry_point."""

    graph_schema_version: str = Field(
        default="1.0",
        min_length=1,
        max_length=32,
        description="AgentForge Graph (AFG) schema revision; JSON in DB is canonical.",
    )
    nodes: list[GraphNode] = Field(min_length=1)
    edges: list[GraphEdge] = Field(default_factory=list)
    entry_point: str = Field(min_length=1, max_length=128)
    parallel_nodes: list[str] = Field(
        default_factory=list,
        description=(
            "Optional hint: node ids intended for parallel execution (orchestrator-specific)."
        ),
    )

    @model_validator(mode="after")
    def _refs(self) -> "GraphDefinitionValidated":
        ids = {n.id for n in self.nodes}
        if self.entry_point not in ids:
            raise ValueError(f"entry_point {self.entry_point!r} not in nodes")
        for e in self.edges:
            if e.from_ not in ids and e.from_ != "START":
                raise ValueError(f"edge from unknown node {e.from_!r}")
            if e.to not in ids and e.to not in ("END",):
                raise ValueError(f"edge to unknown node {e.to!r}")
        for pid in self.parallel_nodes:
            if pid not in ids:
                raise ValueError(f"parallel_nodes references unknown node {pid!r}")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_schema_version": self.graph_schema_version,
            "nodes": [n.model_dump() for n in self.nodes],
            "edges": [e.model_dump(by_alias=True) for e in self.edges],
            "entry_point": self.entry_point,
            "parallel_nodes": list(self.parallel_nodes),
        }


def parse_and_validate_graph(raw: dict[str, Any] | None) -> GraphDefinitionValidated:
    if not raw:
        raw = {}
    nodes = raw.get("nodes")
    if not nodes:
        raise ValueError("graph_definition.nodes must be non-empty")
    edges = raw.get("edges") or []
    entry = raw.get("entry_point")
    if not entry:
        entry = nodes[0]["id"] if isinstance(nodes[0], dict) else nodes[0].id
    parallel_nodes = raw.get("parallel_nodes") or []
    gsv = raw.get("graph_schema_version") or "1.0"
    normalized = {
        "graph_schema_version": gsv,
        "nodes": nodes,
        "edges": edges,
        "entry_point": entry,
        "parallel_nodes": parallel_nodes,
    }
    return GraphDefinitionValidated.model_validate(normalized)
