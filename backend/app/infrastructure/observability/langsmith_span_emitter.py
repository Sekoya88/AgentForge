"""Typed LangSmith span emitter wrapping any ExecutionEventEmitter."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any


class LangsmithSpanEmitter:
    """Wraps an inner emitter and mirrors events to LangSmith runs."""

    def __init__(
        self,
        inner,  # ExecutionEventEmitter
        trace_id: str,
        trace_name: str = "agent_run",
        *,
        api_key: str | None = None,
        project: str | None = None,
    ) -> None:
        self._inner = inner
        self._trace_id = trace_id
        self._trace_name = trace_name
        self._api_key = api_key
        self._project = project
        self._client = None
        self._root_run_id: str | None = None
        self._child_runs: dict[str, str] = {}  # node_id -> run_id
        self._init_client()

    def _init_client(self) -> None:
        try:
            # Set env vars expected by langsmith SDK
            if self._api_key:
                os.environ["LANGCHAIN_API_KEY"] = self._api_key
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
            if self._project:
                os.environ["LANGCHAIN_PROJECT"] = self._project

            from langsmith import Client

            self._client = Client(api_key=self._api_key)
        except Exception:
            self._client = None

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        # Always forward to inner emitter first
        await self._inner.emit(event_type, data)

        if self._client is None:
            return

        try:
            if event_type == "agent_start":
                node_id = data.get("agent_name", "node")
                node_type = data.get("node_type", "llm")
                run = self._client.create_run(
                    id=f"{self._trace_id}-{node_id}",
                    name=node_id,
                    run_type="chain" if node_type != "tool" else "tool",
                    inputs={"preview": data.get("input_preview", "")},
                    extra={"metadata": {"node_type": node_type, "trace_id": self._trace_id}},
                    project_name=self._project,
                )
                self._child_runs[node_id] = (
                    run.id if hasattr(run, "id") else f"{self._trace_id}-{node_id}"
                )

            elif event_type == "agent_end":
                node_id = data.get("agent_name", "node")
                run_id = self._child_runs.pop(node_id, None)
                if run_id:
                    self._client.update_run(
                        run_id,
                        outputs={"preview": data.get("output_preview", "")},
                        extra={"metadata": {"duration_ms": data.get("duration_ms")}},
                        end_time=datetime.now(UTC),
                    )

            elif event_type == "tool_call":
                tool_name = data.get("tool_name", "tool")
                tool_run_id = f"{self._trace_id}-tool-{tool_name}"
                self._client.create_run(
                    id=tool_run_id,
                    name=f"tool:{tool_name}",
                    run_type="tool",
                    inputs=data.get("args", {}),
                    extra={"metadata": {"type": "TOOL", "trace_id": self._trace_id}},
                    project_name=self._project,
                )
                self._client.update_run(
                    tool_run_id,
                    outputs={},
                    end_time=datetime.now(UTC),
                )

            elif event_type == "complete":
                if self._root_run_id:
                    self._client.update_run(
                        self._root_run_id,
                        outputs={"message_count": data.get("message_count")},
                        extra={"metadata": {"total_duration_ms": data.get("total_duration_ms")}},
                        end_time=datetime.now(UTC),
                    )

        except Exception:
            pass  # Never let LangSmith errors break execution
