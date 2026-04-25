from __future__ import annotations

import uuid

from app.infrastructure.persistence.postgres.forge_subagent_repo import ForgeSubAgentRepository
from app.infrastructure.persistence.postgres.models import ForgeSubAgentModel


class SubAgentRegistry:
    """Resolve sub-agent definitions from DB (user override → system fallback)."""

    def __init__(self, repo: ForgeSubAgentRepository) -> None:
        self._repo = repo

    async def get(self, name: str, user_id: uuid.UUID | None = None) -> ForgeSubAgentModel:
        row = await self._repo.get_by_name(name=name, user_id=user_id)
        if row is None:
            raise ValueError(
                f"Sub-agent '{name}' not found. Ensure setup_subagents() ran at startup."
            )
        return row
