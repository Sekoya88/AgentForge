from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.domain.entities.skill import Skill
from app.domain.exceptions import SkillNotFoundError
from app.domain.ports.skill_repository import SkillRepository
from app.domain.skill_source_validation import validate_skill_source
from app.domain.value_objects import SkillParametersSchema


class SkillService:
    def __init__(self, repo: SkillRepository) -> None:
        self._repo = repo

    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        skill_type: str,
        source_code: str,
        instructions: str | None,
        parameters_schema: dict[str, Any],
        permissions: list[str],
        is_public: bool,
    ) -> Skill:
        ps = SkillParametersSchema.model_validate(parameters_schema)
        return await self._repo.create(
            user_id,
            name,
            description,
            skill_type,
            source_code,
            instructions,
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
        skill_type: str | None,
        source_code: str | None,
        instructions: str | None,
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
            skill_type,
            source_code,
            instructions,
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

        # Instruction skills are always valid (no code to check)
        if s.skill_type == "instruction":
            if not s.instructions or not s.instructions.strip():
                await self._repo.set_security_validated(skill_id, user_id, False)
                return {
                    "valid": False,
                    "message": "Instruction skill must have non-empty instructions",
                }
            await self._repo.set_security_validated(skill_id, user_id, True)
            return {"valid": True, "message": "Instruction skill validated"}

        try:
            SkillParametersSchema.model_validate(s.parameters_schema.to_dict())
        except ValidationError as e:
            await self._repo.set_security_validated(skill_id, user_id, False)
            return {"valid": False, "message": f"Invalid parameters_schema: {e}"}

        ok, msg = validate_skill_source(s.source_code)
        await self._repo.set_security_validated(skill_id, user_id, ok)
        return {"valid": ok, "message": msg}
