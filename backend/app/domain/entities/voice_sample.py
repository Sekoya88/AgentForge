from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class VoiceSample:
    id: UUID
    user_id: UUID
    label: str | None
    audio_b64: str
    metadata: dict[str, Any]
    created_at: datetime
