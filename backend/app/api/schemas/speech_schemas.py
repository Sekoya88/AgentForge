from __future__ import annotations

import base64
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.voice_sample import VoiceSample


def _approx_audio_bytes(b64: str) -> int:
    try:
        return len(base64.b64decode(b64, validate=True))
    except Exception:
        return 0


class VoiceSampleCreatedResponse(BaseModel):
    id: UUID
    label: str | None
    created_at: datetime
    metadata: dict[str, Any]
    audio_bytes: int = Field(description="Decoded audio size in bytes")

    @classmethod
    def from_entity(cls, v: VoiceSample) -> VoiceSampleCreatedResponse:
        return cls(
            id=v.id,
            label=v.label,
            created_at=v.created_at,
            metadata=v.metadata,
            audio_bytes=_approx_audio_bytes(v.audio_b64),
        )


class VoiceSampleListItem(BaseModel):
    id: UUID
    label: str | None
    created_at: datetime
    metadata: dict[str, Any]
    audio_bytes: int

    @classmethod
    def from_entity(cls, v: VoiceSample) -> VoiceSampleListItem:
        return cls(
            id=v.id,
            label=v.label,
            created_at=v.created_at,
            metadata=v.metadata,
            audio_bytes=_approx_audio_bytes(v.audio_b64),
        )
