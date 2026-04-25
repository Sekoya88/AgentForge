from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_delegate_to_subagent_tool_calls_runner():
    """Forge _call_delegate_subagent routes to SubAgentRunner."""
    from app.application.services.forge_service import ForgeService

    svc = ForgeService.__new__(ForgeService)
    svc._settings = MagicMock()

    mock_runner = AsyncMock()
    mock_runner.run.return_value = {
        "summary": "Created 1 proposal.",
        "proposals": [],
    }

    with (
        patch(
            "app.infrastructure.subagents.runner.SubAgentRunner",
            return_value=mock_runner,
        ),
        patch(
            "app.infrastructure.subagents.registry.SubAgentRegistry",
        ),
        patch(
            "app.infrastructure.persistence.postgres.forge_subagent_repo.ForgeSubAgentRepository",
        ),
        patch(
            "app.infrastructure.persistence.postgres.session.session_scope",
        ) as mock_scope,
    ):
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await svc._call_delegate_subagent(
            tool_input={"agent_name": "feedback_agent", "task": "Analyse feedback"},
            user_id=uuid.uuid4(),
            anthropic_key="test-key",
        )

    assert isinstance(result, str)
