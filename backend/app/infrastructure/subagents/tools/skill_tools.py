from __future__ import annotations

import uuid

from langchain_core.tools import tool
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.models import SkillModel


def make_skill_tools(user_id: uuid.UUID, session: AsyncSession) -> list:
    """Return skill read/search tools."""

    @tool
    async def search_skills(query: str, limit: int = 10) -> str:
        """Search existing skills by name or description keyword."""
        result = await session.execute(
            select(SkillModel)
            .where(
                or_(
                    SkillModel.user_id == user_id,
                    SkillModel.is_public.is_(True),
                ),
                or_(
                    SkillModel.name.ilike(f"%{query}%"),
                    SkillModel.description.ilike(f"%{query}%"),
                ),
            )
            .limit(limit)
        )
        rows = list(result.scalars().all())
        if not rows:
            return f"No skills found matching '{query}'."
        lines = [f"skill_id={r.id} name={r.name!r} type={r.skill_type}" for r in rows]
        return "\n".join(lines)

    return [search_skills]
