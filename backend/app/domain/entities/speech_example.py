from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SpeechExample:
    id: UUID
    user_id: UUID
    agent_id: UUID | None
    execution_id: UUID | None
    audio_b64: str | None
    transcription: str
    score: float | None
    metadata: dict[str, Any]
    created_at: datetime
    audio_url: str | None = None
