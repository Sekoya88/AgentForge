import uuid

import pytest

from app.infrastructure.memory.noop_memory_store import NoopMemoryStore


@pytest.mark.asyncio
async def test_noop_recall_empty() -> None:
    m = NoopMemoryStore()
    uid = uuid.uuid4()
    aid = uuid.uuid4()
    out = await m.recall(
        user_id=uid,
        agent_id=aid,
        query_embedding=[0.0] * 8,
        top_k=3,
    )
    assert out == []
