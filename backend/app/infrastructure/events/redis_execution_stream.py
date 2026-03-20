import json
from typing import Any
from uuid import UUID

import redis.asyncio as redis

STREAM_MAXLEN = 500


class RedisStreamEmitter:
    """Append-only log in a Redis stream."""

    def __init__(self, client: redis.Redis, stream_key: str) -> None:
        self._r = client
        self._key = stream_key

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data, default=str)
        await self._r.xadd(
            self._key,
            {"type": event_type, "data": payload},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )


def execution_stream_key(execution_id: UUID) -> str:
    return f"exec:{execution_id}"


def sandbox_stream_key(job_id: str) -> str:
    return f"sandbox:{job_id}"
