from typing import Any, Literal, Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field

NodeType = Literal["llm", "tool", "subagent", "conditional", "interrupt"]
ConditionType = Literal["contains", "regex", "json_path", "always"]

class NodeConfig(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    type: str = "llm" # Allow custom plugins so not strictly NodeType
    config: Dict[str, Any] = Field(default_factory=dict)

class EdgeConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from", min_length=1, max_length=128)
    to: str = Field(min_length=1, max_length=128)
    condition: Optional[str] = None
    condition_type: ConditionType = "always"

class GraphDefinition(BaseModel):
    nodes: List[NodeConfig] = Field(default_factory=list)
    edges: List[EdgeConfig] = Field(default_factory=list)
    entry_point: Optional[str] = None
    parallel_nodes: List[str] = Field(default_factory=list)

class SkillSpec(BaseModel):
    name: str
    description: Optional[str] = None
    skill_type: Literal["code", "instruction"] = "instruction"
    source_code: Optional[str] = None
    instructions: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PolicyConfig(BaseModel):
    """Matches backend ExecutionPolicyValidated JSON field names."""

    allowed_tools: Optional[List[str]] = None
    denied_tools: List[str] = Field(default_factory=list)
    allowed_fetch_url_prefixes: Optional[List[str]] = None
    max_graph_steps: Optional[int] = None
    deny_patterns: List[str] = Field(default_factory=list)
    require_human_approval_for: List[str] = Field(default_factory=list)
    max_cost_usd: Optional[float] = None
    max_message_history: Optional[int] = None
    context_compression_threshold: Optional[int] = None

class AgentModelConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.7

class AgentDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = "Local Agent"
    description: Optional[str] = None
    graph_definition: GraphDefinition = Field(default_factory=GraphDefinition)
    llm_model_config: AgentModelConfig = Field(
        default_factory=AgentModelConfig,
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    skills: List[SkillSpec] = Field(default_factory=list)
    execution_policy: Optional[PolicyConfig] = None
