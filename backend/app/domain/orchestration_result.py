from dataclasses import dataclass
from typing import Any

from app.domain.value_objects import MessageDict


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    output_messages: list[MessageDict]
    token_usage: dict[str, Any] | None
    duration_ms: int | None
    interrupt_payload: dict[str, Any] | None = None  # set => execution paused until resume
    output_audio_b64: str | None = None  # e.g. TTS mp3 as base64 from graph state
