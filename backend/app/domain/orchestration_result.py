from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    output_messages: list[dict[str, Any]]
    token_usage: dict[str, Any] | None
    duration_ms: int | None
    """If set, execution should move to `paused` until resume."""
    interrupt_payload: dict[str, Any] | None = None
