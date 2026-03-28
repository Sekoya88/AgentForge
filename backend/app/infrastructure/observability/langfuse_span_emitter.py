"""Typed Langfuse span emitter wrapping any ExecutionEventEmitter."""

from __future__ import annotations

from typing import Any


class LangfuseSpanEmitter:
    """Wraps an inner emitter and mirrors events to typed Langfuse spans."""

    def __init__(
        self,
        inner,  # ExecutionEventEmitter
        trace_id: str,
        trace_name: str = "agent_run",
    ) -> None:
        self._inner = inner
        self._trace_id = trace_id
        self._trace_name = trace_name
        self._spans: dict[str, Any] = {}  # node_id -> active span
        self._langfuse = None
        self._trace = None
        self._init_langfuse()

    def _init_langfuse(self) -> None:
        try:
            from langfuse import Langfuse

            self._langfuse = Langfuse()
            self._trace = self._langfuse.trace(
                id=self._trace_id,
                name=self._trace_name,
            )
        except Exception:
            self._langfuse = None
            self._trace = None

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        # Always forward to inner emitter
        await self._inner.emit(event_type, data)

        # Mirror to Langfuse if configured
        if self._trace is None:
            return

        try:
            if event_type == "agent_start":
                node_id = data.get("agent_name", "node")
                node_type = data.get("node_type", "llm")
                span = self._trace.span(
                    name=node_id,
                    input={"preview": data.get("input_preview", "")},
                    metadata={"node_type": node_type},
                )
                self._spans[node_id] = span

            elif event_type == "agent_end":
                node_id = data.get("agent_name", "node")
                span = self._spans.pop(node_id, None)
                if span:
                    span.end(
                        output={"preview": data.get("output_preview", "")},
                        metadata={"duration_ms": data.get("duration_ms")},
                    )

            elif event_type == "tool_call":
                tool_name = data.get("tool_name", "tool")
                self._trace.span(
                    name=f"tool:{tool_name}",
                    input=data.get("args", {}),
                    metadata={"type": "TOOL"},
                )

            elif event_type == "complete":
                self._trace.update(
                    output={"message_count": data.get("message_count")},
                    metadata={"total_duration_ms": data.get("total_duration_ms")},
                )
                if self._langfuse:
                    self._langfuse.flush()

        except Exception:
            pass  # Never let Langfuse errors break execution
