from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class UserPreferences:
    user_id: UUID
    onboarding_completed: bool = False
    role: str | None = None
    experience_level: str | None = None
    primary_languages: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    response_style: str | None = None
    custom_context: str | None = None
    memory_enabled: bool = True
    memory_compaction_day: int = 0
    memory_compaction_hour: int = 3
    memory_last_compacted_at: datetime | None = None
    memory_next_run_at: datetime | None = None
