import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.subagents.tools.proposal_tools import make_proposal_tools

pytestmark = pytest.mark.asyncio


async def test_create_proposal_tool_stores_proposal():
    user_id = uuid.uuid4()
    mock_repo = AsyncMock()
    mock_repo.create.return_value = MagicMock(id=uuid.uuid4(), title="Test")

    tools = make_proposal_tools(user_id=user_id, proposal_repo=mock_repo)
    create_proposal = next(t for t in tools if t.name == "create_proposal")

    result = await create_proposal.ainvoke(
        {
            "proposal_type": "CREATE_SKILL",
            "title": "Add web_fetch skill",
            "body": "## Rationale\nFetching fails often.",
            "payload": {"name": "web_fetch", "source_code": "def web_fetch(): pass"},
        }
    )

    mock_repo.create.assert_called_once()
    call_kwargs = mock_repo.create.call_args.kwargs
    assert call_kwargs["user_id"] == user_id
    assert call_kwargs["proposal_type"] == "CREATE_SKILL"
    assert "created" in result.lower()
