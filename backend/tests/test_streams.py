import pytest
from fakeredis import aioredis as fa

from app.api.sse import redis_stream_sse
from app.infrastructure.events.redis_execution_stream import RedisStreamEmitter


@pytest.mark.asyncio
async def test_redis_stream_emitter_and_sse_drains() -> None:
    r = await fa.FakeRedis(decode_responses=True)
    ex = RedisStreamEmitter(r, "exec:test-1")
    await ex.emit("agent_start", {"agent_name": "n1"})
    await ex.emit("complete", {"ok": True})

    chunks: list[str] = []
    async for line in redis_stream_sse(r, "exec:test-1"):
        chunks.append(line)

    joined = "".join(chunks)
    assert "agent_start" in joined
    assert "complete" in joined
