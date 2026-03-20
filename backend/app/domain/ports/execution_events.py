from typing import Any, Protocol


class ExecutionEventEmitter(Protocol):
    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish one execution event (e.g. agent_start, tool_call, complete)."""


class NullExecutionEmitter:
    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        _ = event_type
        _ = data
