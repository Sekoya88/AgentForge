from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MemoryEntry:
    id: uuid.UUID
    user_id: uuid.UUID
    agent_id: uuid.UUID
    content: str
    importance: float  # 0.0–1.0
    created_at: datetime
