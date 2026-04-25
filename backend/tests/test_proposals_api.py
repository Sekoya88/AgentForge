from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.approval_service import ApprovalService

pytestmark = pytest.mark.asyncio


async def test_approval_service_create_skill_dispatches_to_skill_service():
    mock_proposal_repo = AsyncMock()
    mock_skill_service = AsyncMock()

    proposal = MagicMock()
    proposal.id = uuid.uuid4()
    proposal.proposal_type = "CREATE_SKILL"
    proposal.status = "pending"
    proposal.payload = {
        "name": "web_fetch",
        "description": "Fetches a URL",
        "source_code": (
            "def web_fetch(url: str) -> str:\n    import httpx\n    return httpx.get(url).text"
        ),
        "parameters_schema": {"type": "object", "properties": {"url": {"type": "string"}}},
    }
    mock_proposal_repo.get.return_value = proposal
    mock_proposal_repo.set_status = AsyncMock(return_value=proposal)
    mock_skill_service.create = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))

    svc = ApprovalService(
        proposal_repo=mock_proposal_repo,
        skill_service=mock_skill_service,
        agent_service=AsyncMock(),
    )

    await svc.apply(proposal_id=proposal.id, user_id=uuid.uuid4())

    mock_skill_service.create.assert_called_once()
    mock_proposal_repo.set_status.assert_called_with(proposal.id, "applied")


async def test_approval_service_reject_sets_rejected_status():
    mock_proposal_repo = AsyncMock()
    proposal = MagicMock()
    proposal.id = uuid.uuid4()
    mock_proposal_repo.get.return_value = proposal
    mock_proposal_repo.set_status = AsyncMock(return_value=proposal)

    svc = ApprovalService(
        proposal_repo=mock_proposal_repo,
        skill_service=AsyncMock(),
        agent_service=AsyncMock(),
    )
    await svc.reject(proposal_id=proposal.id, user_id=uuid.uuid4())

    mock_proposal_repo.set_status.assert_called_with(proposal.id, "rejected")
