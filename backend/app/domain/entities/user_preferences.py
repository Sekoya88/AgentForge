from dataclasses import dataclass, field
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
