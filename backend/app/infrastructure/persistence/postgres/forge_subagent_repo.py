from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.models import ForgeSubAgentModel


class ForgeSubAgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_system(
        self,
        *,
        name: str,
        display_name: str,
        system_prompt: str,
        tools: list[str],
        model_config: dict,
        version: int,
    ) -> ForgeSubAgentModel:
        existing = await self.get_by_name(name=name, user_id=None)
        if existing:
            if existing.version >= version:
                return existing
            existing.display_name = display_name
            existing.system_prompt = system_prompt
            existing.tools = tools
            existing.model_config_json = model_config
            existing.version = version
            await self._session.flush()
            return existing

        row = ForgeSubAgentModel(
            user_id=None,
            name=name,
            display_name=display_name,
            system_prompt=system_prompt,
            tools=tools,
            model_config_json=model_config,
            is_system=True,
            version=version,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_name(self, name: str, user_id: uuid.UUID | None) -> ForgeSubAgentModel | None:
        if user_id is not None:
            result = await self._session.execute(
                select(ForgeSubAgentModel).where(
                    ForgeSubAgentModel.name == name,
                    ForgeSubAgentModel.user_id == user_id,
                )
            )
            row = result.scalar_one_or_none()
            if row:
                return row
        # Fall back to system definition
        result = await self._session.execute(
            select(ForgeSubAgentModel).where(
                ForgeSubAgentModel.name == name,
                ForgeSubAgentModel.user_id.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_system(self) -> list[ForgeSubAgentModel]:
        result = await self._session.execute(
            select(ForgeSubAgentModel).where(ForgeSubAgentModel.user_id.is_(None))
        )
        return list(result.scalars().all())
