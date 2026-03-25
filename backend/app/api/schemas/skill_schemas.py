from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.skill import Skill


class SkillCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    skill_type: Literal["code", "instruction"] = "code"
    source_code: str = Field(default="def run(x: str) -> str:\n    return x\n")
    instructions: str | None = None
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    is_public: bool = False


class SkillUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    skill_type: Literal["code", "instruction"] | None = None
    source_code: str | None = Field(default=None, min_length=1)
    instructions: str | None = None
    parameters_schema: dict[str, Any] | None = None
    permissions: list[str] | None = None
    is_public: bool | None = None


class SkillResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    name: str
    description: str | None
    skill_type: str
    version: str
    source_code: str
    instructions: str | None
    parameters_schema: dict[str, Any]
    permissions: list[str]
    is_public: bool
    security_validated: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, s: Skill) -> "SkillResponse":
        return cls(
            id=s.id,
            user_id=s.user_id,
            name=s.name,
            description=s.description,
            skill_type=s.skill_type,
            version=s.version,
            source_code=s.source_code,
            instructions=s.instructions,
            parameters_schema=s.parameters_schema.to_dict(),
            permissions=s.permissions,
            is_public=s.is_public,
            security_validated=s.security_validated,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


class SkillValidateResponse(BaseModel):
    valid: bool
    message: str
