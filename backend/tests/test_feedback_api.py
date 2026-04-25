from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.feedback_service import FeedbackService

pytestmark = pytest.mark.asyncio


async def test_submit_feedback_persists_in_db():
    mock_repo = AsyncMock()
    mock_repo.create.return_value = MagicMock(
        id=uuid.uuid4(),
        score=0.2,
        category="failure",
        comment="agent crashed",
    )

    svc = FeedbackService(repo=mock_repo)
    result = await svc.submit(
        execution_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        score=0.2,
        comment="agent crashed",
        category="failure",
    )

    mock_repo.create.assert_called_once()
    assert result["score"] == 0.2
