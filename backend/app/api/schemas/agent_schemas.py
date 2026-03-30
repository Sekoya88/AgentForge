from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.value_objects import AgentModelConfig, InterruptConfig, MessageDict


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    graph_definition: GraphDefinitionValidated | dict[str, Any] = Field(default_factory=dict)
    llm_model_config: AgentModelConfig | dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    skills: list[str] = Field(
        default_factory=list,
        description=(
            "Registry skill UUIDs; tool nodes use config.tool_name equal to skill.name. "
            "Built-in tools: echo, fetch, retrieve (RAG over /api/v1/knowledge/ingest)."
        ),
    )
    execution_policy: dict[str, Any] | None = None


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    graph_definition: GraphDefinitionValidated | dict[str, Any] | None = None
    llm_model_config: AgentModelConfig | dict[str, Any] | None = Field(
        default=None,
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    interrupt_config: InterruptConfig | dict[str, Any] | None = None
    status: str | None = None
    skills: list[str] | None = None
    execution_policy: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    user_id: UUID
    name: str
    description: str | None
    graph_definition: Any
    llm_model_config: Any = Field(
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    interrupt_config: Any
    skills: list[str]
    status: str
    security_score: float | None
    created_at: datetime
    updated_at: datetime


class ExecuteAgentRequest(BaseModel):
    input_messages: list[MessageDict | dict[str, Any]] = Field(
        default_factory=lambda: [{"role": "user", "content": "Hello"}]
    )
    run_async: bool = Field(
        default=False,
        description="If true, run in background and stream events via SSE (requires Redis).",
    )
    version: int | None = Field(default=None, description="Execute a specific version snapshot.")
    alias: str | None = Field(
        default=None, description="Execute a specific tagged alias (e.g. 'production')."
    )


class InterruptExecutionRequest(BaseModel):
    decisions: list[dict[str, Any]] = Field(
        default_factory=list,
        description='e.g. [{"type": "approve"}] per §5.1',
    )


class AgentImportYamlRequest(BaseModel):
    yaml_content: str
    name: str | None = None


class AgentImportRequest(BaseModel):
    """Payload from export_agent (versioned)."""

    model_config = ConfigDict(populate_by_name=True)

    version: int = 1
    name: str | None = None
    description: str | None = None
    graph_definition: GraphDefinitionValidated | dict[str, Any] = Field(default_factory=dict)
    llm_model_config: AgentModelConfig | dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    interrupt_config: InterruptConfig | dict[str, Any] | None = None
    skills: list[str] | None = None
    execution_policy: dict[str, Any] | None = None


class ExecutionFeedbackRequest(BaseModel):
    score: float = Field(ge=0, le=1, description="Feedback score between 0 and 1")
    comment: str | None = None


class ExecutionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    user_id: UUID | None
    thread_id: str
    status: str
    input_messages: list[Any]
    output_messages: list[Any] | None
    interrupt_state: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None
    token_usage: dict[str, Any] | None
    duration_ms: int | None
    agent_version_number: int | None = None
    output_audio_b64: str | None = None


class AgentAliasRequest(BaseModel):
    name: str = Field(
        min_length=1, max_length=100, description="Name of the alias, e.g. 'production'"
    )
    version_number: int = Field(ge=1, description="Version number to point the alias to.")
