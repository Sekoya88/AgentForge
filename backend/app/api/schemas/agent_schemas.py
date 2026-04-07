from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.message_content import coerce_message_content_to_str
from app.domain.value_objects import AgentModelConfig, InterruptConfig, MessageDict


class ChatMessage(BaseModel):
    """A single validated chat message returned by an agent execution."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=0)

    @field_validator("content", mode="before")
    @classmethod
    def _coerce_content(cls, v: Any) -> str:
        return coerce_message_content_to_str(v) if not isinstance(v, str) else v


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
    collect_speech_examples: bool | None = Field(
        default=None,
        description="When true, agent allows speech-example collection with user opt-in.",
    )


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
    collect_speech_examples: bool | None = None


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
    collect_speech_examples: bool = False
    inbound_webhook_secret: str | None = None
    inbound_webhook_url: str | None = None
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
    thread_id: str | None = Field(
        default=None, description="Conversation thread_id for stateful multi-turn chat."
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
    input_messages: list[ChatMessage]
    output_messages: list[ChatMessage] | None

    @field_validator("output_messages", "input_messages", mode="before")
    @classmethod
    def _normalize_messages(cls, messages: Any) -> Any:
        if not isinstance(messages, list):
            return messages
        normalized = []
        for msg in messages:
            # Coerce Pydantic models (e.g. MessageDict) to plain dicts
            if hasattr(msg, "model_dump"):
                msg = msg.model_dump()
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, list):
                    msg = {**msg, "content": coerce_message_content_to_str(content)}
            normalized.append(msg)
        return normalized

    interrupt_state: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None
    token_usage: dict[str, Any] | None
    duration_ms: int | None
    agent_version_number: int | None = None
    output_audio_b64: str | None = None
    trigger_source: str = "api"
    schedule_id: UUID | None = None
    compare_group_id: UUID | None = None
    compare_label: str | None = None
    model_config_override: dict[str, Any] | None = None


class AgentCompareVariantRequest(BaseModel):
    label: str = Field(min_length=1, max_length=32)
    model_config_override: dict[str, Any] = Field(
        default_factory=dict,
        description="Shallow merge over the agent's model_config (e.g. temperature).",
    )


class AgentCompareRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32000)
    variants: list[AgentCompareVariantRequest] = Field(min_length=2, max_length=4)
    run_async: bool = Field(
        default=True,
        description="If true, each run streams via SSE like /execute?run_async=true.",
    )


class AgentCompareResponse(BaseModel):
    compare_group_id: UUID
    executions: list[ExecutionResponse]


class AgentScheduleCreateRequest(BaseModel):
    cron_expression: str = Field(min_length=1, max_length=128)
    input: dict[str, Any] = Field(
        default_factory=dict,
        description='Optional payload; include "input_messages" for chat-style runs.',
    )
    alias: str | None = Field(default=None, max_length=100)
    enabled: bool = True


class AgentScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cron_expression: str | None = Field(default=None, min_length=1, max_length=128)
    input: dict[str, Any] | None = None
    alias: str | None = Field(default=None, max_length=100)
    enabled: bool | None = None


class AgentScheduleResponse(BaseModel):
    id: UUID
    agent_id: UUID
    user_id: UUID | None
    alias: str | None
    cron_expression: str
    input: dict[str, Any]
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime
    created_at: datetime


class AgentAliasRequest(BaseModel):
    name: str = Field(
        min_length=1, max_length=100, description="Name of the alias, e.g. 'production'"
    )
    version_number: int = Field(ge=1, description="Version number to point the alias to.")


class AgentImportBundle(BaseModel):
    agentforge_version: str
    agent: dict  # Flexible — validated downstream
    skills: list[dict] = Field(default_factory=list)


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    thread_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None
    message_count: int
