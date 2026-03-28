from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.skill import Skill
from app.domain.ports.skill_repository import SkillRepository
from app.domain.value_objects import SkillParametersSchema
from app.infrastructure.persistence.postgres.models import SkillModel, UserModel


class PostgresSkillRepository(SkillRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        skill_type: str,
        source_code: str,
        instructions: str | None,
        parameters_schema: SkillParametersSchema,
        permissions: list[str],
        is_public: bool,
    ) -> Skill:
        m = SkillModel(
            user_id=user_id,
            name=name,
            description=description,
            skill_type=skill_type,
            version="1.0.0",
            source_code=source_code,
            instructions=instructions,
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

    async def list_public_registry(
        self, search: str | None, *, limit: int = 100
    ) -> list[tuple[Skill, str | None]]:
        cap = min(max(limit, 1), 500)
        conditions = [SkillModel.is_public.is_(True)]
        if search and search.strip():
            term = f"%{search.strip()}%"
            conditions.append(
                or_(
                    SkillModel.name.ilike(term),
                    SkillModel.description.ilike(term),
                )
            )
        q = await self._session.execute(
            select(SkillModel, UserModel.display_name, UserModel.email)
            .outerjoin(UserModel, SkillModel.user_id == UserModel.id)
            .where(and_(*conditions))
            .order_by(SkillModel.created_at.desc())
            .limit(cap)
        )
        out: list[tuple[Skill, str | None]] = []
        for row in q.all():
            m, display_name, email = row[0], row[1], row[2]
            skill = self._to_entity(m)
            author: str | None = None
            if display_name and str(display_name).strip():
                author = str(display_name).strip()
            elif email:
                author = str(email).split("@", 1)[0]
            out.append((skill, author))
        return out

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
        skill_type: str | None,
        source_code: str | None,
        instructions: str | None,
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
        if skill_type is not None:
            m.skill_type = skill_type
        if source_code is not None:
            m.source_code = source_code
        if instructions is not None:
            m.instructions = instructions
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
            skill_type=getattr(m, "skill_type", None) or "code",
            version=m.version or "1.0.0",
            source_code=m.source_code,
            instructions=getattr(m, "instructions", None),
            parameters_schema=SkillParametersSchema.model_validate(m.parameters_schema or {}),
            permissions=perms,
            is_public=bool(m.is_public),
            security_validated=bool(m.security_validated),
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
