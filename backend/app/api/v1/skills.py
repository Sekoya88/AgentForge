from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.schemas.skill_schemas import (
    SkillCreateRequest,
    SkillResponse,
    SkillUpdateRequest,
    SkillValidateResponse,
)
from app.application.services.skill_service import SkillService
from app.dependencies import get_current_user, get_skill_service
from app.domain.entities.user import User

router = APIRouter(prefix="/skills", tags=["skills"])


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SkillService, Depends(get_skill_service)],
) -> SkillResponse:
    s = await svc.create(
        user.id,
        body.name,
        body.description,
        body.source_code,
        body.parameters_schema,
        body.permissions,
        body.is_public,
    )
    return SkillResponse.from_entity(s)


@router.get("", response_model=list[SkillResponse])
async def list_skills(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SkillService, Depends(get_skill_service)],
) -> list[SkillResponse]:
    items = await svc.list_skills(user.id)
    return [SkillResponse.from_entity(s) for s in items]


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SkillService, Depends(get_skill_service)],
) -> SkillResponse:
    s = await svc.get(UUID(skill_id), user.id)
    return SkillResponse.from_entity(s)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    body: SkillUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SkillService, Depends(get_skill_service)],
) -> SkillResponse:
    s = await svc.update(
        UUID(skill_id),
        user.id,
        body.name,
        body.description,
        body.source_code,
        body.parameters_schema,
        body.permissions,
        body.is_public,
    )
    return SkillResponse.from_entity(s)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SkillService, Depends(get_skill_service)],
) -> None:
    await svc.delete(UUID(skill_id), user.id)


@router.post("/{skill_id}/validate", response_model=SkillValidateResponse)
async def validate_skill(
    skill_id: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SkillService, Depends(get_skill_service)],
) -> SkillValidateResponse:
    out = await svc.validate(UUID(skill_id), user.id)
    return SkillValidateResponse(valid=out["valid"], message=out["message"])
