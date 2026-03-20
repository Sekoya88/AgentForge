from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings

_pool: Optional[AsyncConnectionPool] = None


async def setup_checkpoint_pool() -> None:
    global _pool
    settings = get_settings()
    url = settings.database_url.replace("+asyncpg", "").replace("+psycopg2", "")
    _pool = AsyncConnectionPool(url, kwargs={"autocommit": True}, open=False)
    await _pool.open()
    checkpointer = AsyncPostgresSaver(_pool)
    await checkpointer.setup()


async def teardown_checkpoint_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_checkpointer() -> AsyncGenerator[AsyncPostgresSaver, None]:
    if _pool is None:
        raise RuntimeError("Checkpoint pool not initialized")
    yield AsyncPostgresSaver(_pool)
