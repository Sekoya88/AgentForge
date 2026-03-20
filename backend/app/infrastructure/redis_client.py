import logging

import redis.asyncio as redis

log = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis | None:
    return _client


async def connect_redis(url: str) -> None:
    global _client
    try:
        r = redis.from_url(url, decode_responses=True)
        await r.ping()
        _client = r
        log.info("redis_connected")
    except Exception as e:
        _client = None
        log.warning("redis_unavailable", extra={"error": str(e)})


async def disconnect_redis() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
