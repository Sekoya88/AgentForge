from typing import Any
from uuid import UUID

from app.domain.entities.skill import Skill
from app.domain.exceptions import SkillNotFoundError
from app.domain.ports.skill_repository import SkillRepository
from app.domain.value_objects import SkillParametersSchema


class SkillService:
    def __init__(self, repo: SkillRepository) -> None:
        self._repo = repo

    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        source_code: str,
        parameters_schema: dict[str, Any],
        permissions: list[str],
        is_public: bool,
    ) -> Skill:
        ps = SkillParametersSchema.model_validate(parameters_schema)
        return await self._repo.create(
            user_id,
            name,
            description,
            source_code,
            ps,
            permissions,
            is_public,
        )

    async def list_skills(self, user_id: UUID) -> list[Skill]:
        return await self._repo.list_visible(user_id)

    async def get(self, skill_id: UUID, user_id: UUID) -> Skill:
        s = await self._repo.get_by_id(skill_id, user_id)
        if s is None:
            raise SkillNotFoundError(str(skill_id))
        return s

    async def update(
        self,
        skill_id: UUID,
        user_id: UUID,
        name: str | None,
        description: str | None,
        source_code: str | None,
        parameters_schema: dict[str, Any] | None,
        permissions: list[str] | None,
        is_public: bool | None,
    ) -> Skill:
        ps = (
            SkillParametersSchema.model_validate(parameters_schema)
            if parameters_schema is not None
            else None
        )
        s = await self._repo.update(
            skill_id,
            user_id,
            name,
            description,
            source_code,
            ps,
            permissions,
            is_public,
        )
        if s is None:
            raise SkillNotFoundError(str(skill_id))
        return s

    async def delete(self, skill_id: UUID, user_id: UUID) -> None:
        ok = await self._repo.delete(skill_id, user_id)
        if not ok:
            raise SkillNotFoundError(str(skill_id))

    async def validate(self, skill_id: UUID, user_id: UUID) -> dict[str, Any]:
        s = await self._repo.get_by_id(skill_id, user_id)
        if s is None or s.user_id != user_id:
            raise SkillNotFoundError(str(skill_id))
        await self._repo.set_security_validated(skill_id, user_id, True)
        return {
            "valid": True,
            "message": "Stub validator — marked security_validated=true (replace with real checks)",
        }
