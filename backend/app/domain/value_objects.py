from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.graph_definition import GraphDefinitionValidated


class GeneratedAgent(BaseModel):
    name: str
    description: str
    agent_model_config: "AgentModelConfig" = Field(alias="model_config")
    graph_definition: GraphDefinitionValidated

    model_config = ConfigDict(populate_by_name=True)


class GeneratedSkill(BaseModel):
    name: str
    description: str
    source_code: str
    parameters_schema: "SkillParametersSchema"
    permissions: list[str]


class AgentModelConfig(BaseModel):
    provider: Literal["mock", "openai", "google", "gemini"] = "mock"
    model: str = "gpt-5.4-mini"
    temperature: float | None = None
    # We allow extra fields (e.g. max_tokens, etc.) in case the user wants to pass them
    model_config = ConfigDict(extra="ignore")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class InterruptConfig(BaseModel):
    allowed_decisions: list[str] = Field(default_factory=list)
    timeout_seconds: int | None = None
    model_config = ConfigDict(extra="ignore")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class MessageDict(BaseModel):
    role: str
    content: str
    model_config = ConfigDict(extra="ignore")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class SkillParametersSchema(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="ignore")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class CampaignConfig(BaseModel):
    target_url: str | None = None
    max_duration_minutes: int | None = None
    attack_vectors: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="ignore")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class FinetuneHyperparams(BaseModel):
    epochs: int | None = None
    learning_rate: float | None = None
    batch_size: int | None = None
    model_config = ConfigDict(extra="ignore")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
