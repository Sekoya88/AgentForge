from dataclasses import dataclass
from typing import Any

from app.domain.value_objects import MessageDict


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    output_messages: list[MessageDict]
    token_usage: dict[str, Any] | None
    duration_ms: int | None
    """If set, execution should move to `paused` until resume."""
    interrupt_payload: dict[str, Any] | None = None
