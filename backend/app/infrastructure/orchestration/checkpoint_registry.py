"""In-memory LangGraph checkpointers keyed by execution (dev / single-worker)."""

from threading import Lock
from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver

_lock = Lock()
_store: dict[str, InMemorySaver] = {}


def put_saver(execution_id: UUID, saver: InMemorySaver) -> None:
    with _lock:
        _store[str(execution_id)] = saver


def get_saver(execution_id: UUID) -> InMemorySaver | None:
    with _lock:
        return _store.get(str(execution_id))


def pop_saver(execution_id: UUID) -> None:
    with _lock:
        _store.pop(str(execution_id), None)
