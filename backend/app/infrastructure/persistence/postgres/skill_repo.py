from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.skill import Skill
from app.domain.ports.skill_repository import SkillRepository
from app.domain.value_objects import SkillParametersSchema
from app.infrastructure.persistence.postgres.models import SkillModel


class PostgresSkillRepository(SkillRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        source_code: str,
        parameters_schema: SkillParametersSchema,
        permissions: list[str],
        is_public: bool,
    ) -> Skill:
        m = SkillModel(
            user_id=user_id,
            name=name,
            description=description,
            version="1.0.0",
            source_code=source_code,
            parameters_schema=parameters_schema.to_dict(),
            permissions=permissions,
            is_public=is_public,
            security_validated=False,
        )
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)

    async def list_visible(self, user_id: UUID) -> list[Skill]:
        q = await self._session.execute(
            select(SkillModel)
            .where(or_(SkillModel.is_public.is_(True), SkillModel.user_id == user_id))
            .order_by(SkillModel.created_at.desc())
        )
        return [self._to_entity(r) for r in q.scalars().all()]

    async def get_by_id(self, skill_id: UUID, user_id: UUID) -> Skill | None:
        m = await self._session.get(SkillModel, skill_id)
        if m is None:
            return None
        if not m.is_public and m.user_id != user_id:
            return None
        return self._to_entity(m)

    async def update(
        self,
        skill_id: UUID,
        user_id: UUID,
        name: str | None,
        description: str | None,
        source_code: str | None,
        parameters_schema: SkillParametersSchema | None,
        permissions: list[str] | None,
        is_public: bool | None,
    ) -> Skill | None:
        m = await self._session.get(SkillModel, skill_id)
        if m is None or m.user_id != user_id:
            return None
        if name is not None:
            m.name = name
        if description is not None:
            m.description = description
        if source_code is not None:
            m.source_code = source_code
        if parameters_schema is not None:
            m.parameters_schema = parameters_schema.to_dict()
        if permissions is not None:
            m.permissions = permissions
        if is_public is not None:
            m.is_public = is_public
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)

    async def delete(self, skill_id: UUID, user_id: UUID) -> bool:
        m = await self._session.get(SkillModel, skill_id)
        if m is None or m.user_id != user_id:
            return False
        await self._session.delete(m)
        return True

    async def set_security_validated(self, skill_id: UUID, user_id: UUID, value: bool) -> bool:
        m = await self._session.get(SkillModel, skill_id)
        if m is None or m.user_id != user_id:
            return False
        m.security_validated = value
        await self._session.flush()
        return True

    @staticmethod
    def _to_entity(m: SkillModel) -> Skill:
        perms = list(m.permissions) if m.permissions is not None else []
        return Skill(
            id=m.id,
            user_id=m.user_id,
            name=m.name,
            description=m.description,
            version=m.version or "1.0.0",
            source_code=m.source_code,
            parameters_schema=SkillParametersSchema.model_validate(m.parameters_schema or {}),
            permissions=perms,
            is_public=bool(m.is_public),
            security_validated=bool(m.security_validated),
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
