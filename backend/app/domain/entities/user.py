from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    display_name: str | None
    collect_speech_examples: bool
    created_at: datetime
    updated_at: datetime
    execution_rate_limit: int = 60
