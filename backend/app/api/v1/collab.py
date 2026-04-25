"""Real-time collaborative builder — WebSocket cursor presence.

Each authenticated client joins a "room" identified by agent_id.
Messages are broadcast via Redis pub/sub so multiple server instances work.

Protocol (JSON over WebSocket):
  Client → Server:
    {"type": "cursor", "x": float, "y": float}         — cursor position update
    {"type": "selection", "node_id": str | null}         — node selection
    {"type": "ping"}                                     — keepalive

  Server → Client:
    {"type": "presence", "users": [{"user_id", "display_name", "x", "y", "node_id"}]}
    {"type": "joined", "user_id": str, "display_name": str}
    {"type": "left", "user_id": str}
    {"type": "pong"}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.dependencies import get_redis_optional

log = logging.getLogger(__name__)
router = APIRouter(prefix="/collab", tags=["collab"])

_PRESENCE_TTL = 30  # seconds


def _room_channel(agent_id: str) -> str:
    return f"collab:room:{agent_id}"


def _presence_key(agent_id: str) -> str:
    return f"collab:presence:{agent_id}"


async def _publish(r: redis.Redis, agent_id: str, msg: dict) -> None:
    await r.publish(_room_channel(agent_id), json.dumps(msg))


async def _set_presence(r: redis.Redis, agent_id: str, user_id: str, data: dict) -> None:
    await r.hset(_presence_key(agent_id), user_id, json.dumps(data))
    await r.expire(_presence_key(agent_id), _PRESENCE_TTL * 4)


async def _remove_presence(r: redis.Redis, agent_id: str, user_id: str) -> None:
    await r.hdel(_presence_key(agent_id), user_id)


async def _get_presence(r: redis.Redis, agent_id: str) -> list[dict]:
    raw = await r.hgetall(_presence_key(agent_id))
    users = []
    for v in raw.values():
        try:
            users.append(json.loads(v))
        except Exception:
            pass
    return users


@router.websocket("/agents/{agent_id}")
async def collab_ws(
    websocket: WebSocket,
    agent_id: UUID,
    r: Annotated[redis.Redis | None, Depends(get_redis_optional)],
) -> None:
    """WebSocket endpoint for cursor presence in the agent builder."""
    # Auth via query param token (WebSocket can't use Authorization header easily)
    token = websocket.query_params.get("token")
    if not token or r is None:
        await websocket.close(code=4001, reason="Unauthorized or Redis unavailable")
        return

    # Validate token and get user
    from app.config import get_settings
    from app.infrastructure.auth.jwt_handler import decode_token
    from app.infrastructure.persistence.postgres.session import get_session_factory
    from app.infrastructure.persistence.postgres.user_repo import PostgresUserRepository

    try:
        settings = get_settings()
        uid = decode_token(token, settings, expect_typ="access")
        factory = get_session_factory()
        async with factory() as session:
            user_repo = PostgresUserRepository(session)
            user = await user_repo.get_by_id(uid)
        if user is None:
            await websocket.close(code=4001, reason="User not found")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    aid = str(agent_id)
    uid_str = str(user.id)
    display = user.display_name or user.email.split("@")[0]

    initial_state = {"user_id": uid_str, "display_name": display, "x": 0, "y": 0, "node_id": None}
    await _set_presence(r, aid, uid_str, initial_state)
    await _publish(r, aid, {"type": "joined", "user_id": uid_str, "display_name": display})

    # Send current presence snapshot to the new client
    presence = await _get_presence(r, aid)
    await websocket.send_json({"type": "presence", "users": presence})

    pubsub = r.pubsub()
    await pubsub.subscribe(_room_channel(aid))

    async def _recv_from_redis() -> None:
        """Forward Redis pub/sub messages to this WebSocket client."""
        try:
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                try:
                    data = json.loads(msg["data"])
                except Exception:
                    continue
                # Don't echo own join/cursor back
                if data.get("user_id") == uid_str and data.get("type") == "cursor":
                    continue
                try:
                    await websocket.send_json(data)
                except Exception:
                    break
        except Exception:
            pass

    redis_task = asyncio.create_task(_recv_from_redis())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "cursor":
                state = {
                    "user_id": uid_str,
                    "display_name": display,
                    "x": float(msg.get("x", 0)),
                    "y": float(msg.get("y", 0)),
                    "node_id": initial_state.get("node_id"),
                }
                initial_state.update(state)
                await _set_presence(r, aid, uid_str, state)
                await _publish(r, aid, {"type": "cursor", **state})

            elif msg_type == "selection":
                initial_state["node_id"] = msg.get("node_id")
                await _set_presence(r, aid, uid_str, initial_state)
                await _publish(
                    r,
                    aid,
                    {"type": "selection", "user_id": uid_str, "node_id": msg.get("node_id")},
                )

    except WebSocketDisconnect:
        pass
    finally:
        redis_task.cancel()
        await pubsub.unsubscribe(_room_channel(aid))
        await _remove_presence(r, aid, uid_str)
        await _publish(r, aid, {"type": "left", "user_id": uid_str})
