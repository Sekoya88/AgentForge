from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.domain.entities.skill import Skill


class SkillRepository(ABC):
    @abstractmethod
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
        pass

    @abstractmethod
    async def list_visible(self, user_id: UUID) -> list[Skill]:
        pass

    @abstractmethod
    async def get_by_id(self, skill_id: UUID, user_id: UUID) -> Skill | None:
        """User's own skill or public skill."""

    @abstractmethod
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
    ) -> Skill | None:
        pass

    @abstractmethod
    async def delete(self, skill_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    async def set_security_validated(self, skill_id: UUID, user_id: UUID, value: bool) -> bool:
        pass
