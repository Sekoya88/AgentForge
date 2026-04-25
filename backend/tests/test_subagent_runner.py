import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_runner_returns_summary_and_proposals():
    from app.infrastructure.subagents.runner import SubAgentRunner

    mock_definition = MagicMock()
    mock_definition.name = "feedback_agent"
    mock_definition.system_prompt = "You synthesise feedback."
    mock_definition.tools = ["get_feedback_summary", "create_proposal"]
    mock_definition.model_config_json = {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "temperature": 0.3,
    }

    mock_registry = AsyncMock()
    mock_registry.get.return_value = mock_definition

    with patch(
        "app.infrastructure.subagents.runner.SubAgentRunner._invoke_graph",
        new_callable=AsyncMock,
        return_value={"summary": "Created 1 proposal.", "proposals": [{"title": "Fix skill"}]},
    ):
        runner = SubAgentRunner(registry=mock_registry, session=AsyncMock(), user_id=uuid.uuid4())
        result = await runner.run(agent_name="feedback_agent", task="Analyse feedback for agent X")

    assert "summary" in result
    assert result["summary"] == "Created 1 proposal."
