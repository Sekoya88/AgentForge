"""Mirror of AgentForge backend graph_definition validation (standalone SDK)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NodeType = Literal["llm", "tool", "subagent", "conditional", "interrupt"]


class GraphNode(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    type: NodeType = "llm"
    config: dict[str, Any] = Field(default_factory=dict)


ConditionType = Literal["contains", "regex", "json_path", "always"]


class GraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from", min_length=1, max_length=128)
    to: str = Field(min_length=1, max_length=128)
    condition: str | None = None
    condition_type: ConditionType = "contains"


class GraphDefinitionValidated(BaseModel):
    nodes: list[GraphNode] = Field(min_length=1)
    edges: list[GraphEdge] = Field(default_factory=list)
    entry_point: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _refs(self) -> "GraphDefinitionValidated":
        ids = {n.id for n in self.nodes}
        if self.entry_point not in ids:
            raise ValueError(f"entry_point {self.entry_point!r} not in nodes")
        for e in self.edges:
            if e.from_ not in ids:
                raise ValueError(f"edge from unknown node {e.from_!r}")
            if e.to not in ids:
                raise ValueError(f"edge to unknown node {e.to!r}")
        return self


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
    normalized = {"nodes": nodes, "edges": edges, "entry_point": entry}
    return GraphDefinitionValidated.model_validate(normalized)
