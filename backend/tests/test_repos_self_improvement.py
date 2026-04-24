import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.persistence.postgres.execution_feedback_repo import (
    ExecutionFeedbackRepository,
)
from app.infrastructure.persistence.postgres.forge_subagent_repo import ForgeSubAgentRepository
from app.infrastructure.persistence.postgres.meta_proposal_repo import MetaProposalRepository
from app.infrastructure.persistence.postgres.models import ForgeSubAgentModel

pytestmark = pytest.mark.asyncio


async def test_forge_subagent_repo_get_by_name_returns_system_fallback():
    """get_by_name falls back to system definition when no user override exists."""
    mock_session = AsyncMock()
    system_row = MagicMock(spec=ForgeSubAgentModel)
    system_row.name = "skill_builder"
    system_row.is_system = True

    # First query (user-specific) returns None, second (system) returns the row
    execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=system_row)),
    ]
    mock_session.execute = AsyncMock(side_effect=execute_results)

    repo = ForgeSubAgentRepository(mock_session)
    result = await repo.get_by_name(name="skill_builder", user_id=uuid.uuid4())
    assert result is not None
    assert result.name == "skill_builder"
    assert result.is_system is True


async def test_forge_subagent_repo_get_by_name_without_user():
    """get_by_name with user_id=None goes straight to system fallback."""
    mock_session = AsyncMock()
    system_row = MagicMock(spec=ForgeSubAgentModel)
    system_row.name = "meta_agent"
    system_row.is_system = True

    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=system_row))
    )

    repo = ForgeSubAgentRepository(mock_session)
    result = await repo.get_by_name(name="meta_agent", user_id=None)
    assert result is not None
    assert result.name == "meta_agent"


async def test_meta_proposal_repo_create_sets_pending_status():
    """MetaProposalRepository.create() always sets status=pending."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    repo = MetaProposalRepository(mock_session)
    result = await repo.create(
        user_id=uuid.uuid4(),
        proposal_type="CREATE_SKILL",
        title="Add web_fetch",
        body="Rationale",
        payload={"name": "web_fetch"},
        source="on_demand",
    )

    assert result.status == "pending"
    assert result.proposal_type == "CREATE_SKILL"
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


async def test_execution_feedback_repo_create():
    """ExecutionFeedbackRepository.create() stores the row and returns it."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    repo = ExecutionFeedbackRepository(mock_session)
    result = await repo.create(
        execution_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        score=0.4,
        comment="slow",
        category="speed",
    )

    assert result.score == 0.4
    assert result.category == "speed"
    mock_session.add.assert_called_once()
