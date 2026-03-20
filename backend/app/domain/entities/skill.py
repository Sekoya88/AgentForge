from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Skill:
    id: UUID
    user_id: UUID | None
    name: str
    description: str | None
    version: str
    source_code: str
    parameters_schema: dict[str, Any]
    permissions: list[str]
    is_public: bool
    security_validated: bool
    created_at: datetime
    updated_at: datetime
