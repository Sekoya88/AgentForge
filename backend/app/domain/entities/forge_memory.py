from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class ForgeMemoryChunk:
    user_id: UUID
    content: str
    embedding: list[float]
    period_start: datetime
    period_end: datetime
    source_conv_ids: list[str] = field(default_factory=list)
    id: UUID | None = None
    created_at: datetime | None = None
