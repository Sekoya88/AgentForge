from __future__ import annotations

import uuid
from typing import Any

from app.infrastructure.persistence.postgres.meta_proposal_repo import MetaProposalRepository


class ApprovalService:
    def __init__(
        self,
        proposal_repo: MetaProposalRepository,
        skill_service,
        agent_service,
    ) -> None:
        self._proposals = proposal_repo
        self._skills = skill_service
        self._agents = agent_service

    async def apply(self, proposal_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        proposal = await self._proposals.get(proposal_id, user_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != "pending":
            raise ValueError(f"Proposal is already {proposal.status}")

        ptype = proposal.proposal_type
        payload = proposal.payload

        if ptype == "CREATE_SKILL":
            await self._skills.create(
                user_id=user_id,
                name=payload["name"],
                description=payload.get("description", ""),
                skill_type="code",
                source_code=payload.get("source_code", ""),
                parameters_schema=payload.get("parameters_schema", {}),
                permissions=payload.get("permissions", []),
                is_public=False,
            )
        elif ptype == "UPDATE_SKILL":
            skill_id = uuid.UUID(payload["skill_id"])
            await self._skills.update(
                skill_id=skill_id,
                user_id=user_id,
                updates={"source_code": payload.get("source_code")},
            )
        elif ptype == "UPDATE_AGENT_PROMPT":
            agent_id = uuid.UUID(payload["agent_id"])
            patch = payload.get("system_prompt_patch", "")
            agent = await self._agents.get(agent_id=agent_id, user_id=user_id)
            gd = agent.graph_definition or {}
            nodes = gd.get("nodes", [])
            for node in nodes:
                if node.get("type") == "llm":
                    node["system_prompt"] = patch
                    break
            await self._agents.update(
                agent_id=agent_id, user_id=user_id, updates={"graph_definition": gd}
            )
        elif ptype == "CREATE_KNOWLEDGE":
            pass  # Extend when KnowledgeService is available

        await self._proposals.set_status(proposal_id, "applied")
        return {"status": "applied", "proposal_id": str(proposal_id)}

    async def reject(self, proposal_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        proposal = await self._proposals.get(proposal_id, user_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        await self._proposals.set_status(proposal_id, "rejected")
        return {"status": "rejected", "proposal_id": str(proposal_id)}
