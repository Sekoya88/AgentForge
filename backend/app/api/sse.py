from collections.abc import AsyncIterator

import redis.asyncio as redis


def _sse_line(fields: dict[str, str]) -> str:
    typ = fields.get("type") or "message"
    data = fields.get("data") or "{}"
    return f"event: {typ}\ndata: {data}\n\n"


def _is_terminal(fields: dict[str, str]) -> bool:
    return fields.get("type") in ("complete", "error")


async def redis_stream_sse(client: redis.Redis, stream_key: str) -> AsyncIterator[str]:
    last_id = "0-0"
    history = await client.xrange(stream_key)
    for entry_id, fields in history:
        last_id = entry_id
        yield _sse_line(fields)
        if _is_terminal(fields):
            return

    while True:
        block = await client.xread({stream_key: last_id}, block=3000, count=100)
        if not block:
            yield ": ping\n\n"
            continue
        for _name, rows in block:
            for entry_id, fields in rows:
                last_id = entry_id
                yield _sse_line(fields)
                if _is_terminal(fields):
                    return
