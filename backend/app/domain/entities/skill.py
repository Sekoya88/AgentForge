from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.value_objects import SkillParametersSchema


@dataclass(frozen=True, slots=True)
class Skill:
    id: UUID
    user_id: UUID | None
    name: str
    description: str | None
    version: str
    source_code: str
    parameters_schema: SkillParametersSchema
    permissions: list[str]
    is_public: bool
    security_validated: bool
    created_at: datetime
    updated_at: datetime
