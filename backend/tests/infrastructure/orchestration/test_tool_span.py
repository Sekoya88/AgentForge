"""Verify @observe-wrapped tool dispatch calls through to handlers."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_observed_tool_dispatch_calls_underlying():
    """_observed_tool_dispatch must call through to the actual tool logic."""
    from app.infrastructure.orchestration.langgraph_orchestrator import _observed_tool_dispatch

    mock_handler = AsyncMock(return_value="tool_result")

    with patch(
        "app.infrastructure.orchestration.langgraph_orchestrator._langfuse_update_current_span",
    ):
        result = await _observed_tool_dispatch(
            tool_name="weather_search",
            arg="London",
            handler=mock_handler,
        )

    mock_handler.assert_awaited_once_with("London")
    assert result == "tool_result"
