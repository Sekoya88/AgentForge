from __future__ import annotations

import uuid

from langchain_core.tools import tool

from app.infrastructure.persistence.postgres.meta_proposal_repo import MetaProposalRepository


def make_proposal_tools(
    user_id: uuid.UUID,
    proposal_repo: MetaProposalRepository,
) -> list:
    """Return LangChain tools bound to this user's repo context."""

    @tool
    async def create_proposal(
        proposal_type: str,
        title: str,
        body: str,
        payload: dict,
        agent_id: str | None = None,
        skill_id: str | None = None,
    ) -> str:
        """Create a proposal for the user to review and approve.

        proposal_type: CREATE_SKILL | UPDATE_SKILL | CREATE_KNOWLEDGE | UPDATE_AGENT_PROMPT
        title: short title shown in UI
        body: markdown explanation for the user
        payload: the change to apply if approved (varies by proposal_type)
        agent_id: UUID of the affected agent (optional)
        skill_id: UUID of the affected skill (optional)
        """
        row = await proposal_repo.create(
            user_id=user_id,
            proposal_type=proposal_type,
            title=title,
            body=body,
            payload=payload,
            source="on_demand",
            agent_id=uuid.UUID(agent_id) if agent_id else None,
            skill_id=uuid.UUID(skill_id) if skill_id else None,
        )
        return f"Proposal '{title}' created (id={row.id}). Awaiting user review."

    return [create_proposal]
