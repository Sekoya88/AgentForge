import pytest
from fakeredis import aioredis as fa

from app.api.sse import redis_stream_sse
from app.infrastructure.events.redis_execution_stream import RedisStreamEmitter


@pytest.mark.asyncio
async def test_redis_stream_sse_resume_after_skips_prior() -> None:
    r = await fa.FakeRedis(decode_responses=True)
    key = "exec:resume-test"
    ex = RedisStreamEmitter(r, key)
    await ex.emit("a", {"i": 1})
    await ex.emit("b", {"i": 2})
    await ex.emit("complete", {"ok": True})

    entries = await r.xrange(key)
    assert len(entries) >= 2
    first_id = entries[0][0]

    chunks2: list[str] = []
    async for line in redis_stream_sse(r, key, resume_after=first_id):
        chunks2.append(line)
    joined2 = "".join(chunks2)
    assert "event: a" not in joined2
    assert "complete" in joined2
