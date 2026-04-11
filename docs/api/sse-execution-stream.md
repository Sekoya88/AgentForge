# SSE — agent / forge / sandbox execution streams

## Routes (Redis stream backend)

| Route | Redis key pattern |
|-------|-------------------|
| `GET /api/v1/agents/{agent_id}/stream/{execution_id}` | `exec:{execution_id}` |
| `GET /api/v1/forge/stream/{execution_id}` | `exec:{execution_id}` |
| `GET /api/v1/sandbox/stream/{job_id}` | `sandbox:{job_id}` |

Fine-tune job streaming uses **Pub/Sub**, not this Redis stream pattern — see `GET /api/v1/finetune/{job_id}/stream`.

## Event shape

- Stream entries are Redis `XADD` fields: `type` (event name), `data` (JSON string).
- SSE frames may include an **`id:`** line with the Redis stream entry ID for resume.
- **Terminal events:** `type` in `complete`, `error` — server stops iterating after emitting them.
- **Keepalive:** comment line `: ping` when `XREAD` blocks time out (idle).

## Resume

- Query **`after_id`**: last Redis stream ID the client already applied. Server replays only entries **after** that ID (`XRANGE` exclusive min + `XREAD`).
- Clients should append `after_id` when reconnecting after network errors; see `frontend/src/lib/sse.ts` (`consumeSsePathWithRetry`).

## Limits

- Streams use `MAXLEN ~500` (approximate trimming) — see `redis_execution_stream.py`.
