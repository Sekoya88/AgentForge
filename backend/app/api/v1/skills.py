from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.skill_schemas import (
    SkillCreateRequest,
    SkillResponse,
    SkillUpdateRequest,
    SkillValidateResponse,
)
from app.application.services.skill_service import SkillService
from app.dependencies import get_current_user, get_skill_service
from app.domain.entities.user import User
from app.domain.skill_templates import SKILL_TEMPLATES, get_templates_by_category

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
        body.skill_type,
        body.source_code,
        body.instructions,
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


# ── Template routes (before /{skill_id} to avoid path conflict) ──


@router.get("/templates/list", response_model=list[dict[str, Any]])
async def list_skill_templates() -> list[dict[str, Any]]:
    return SKILL_TEMPLATES


@router.get("/templates/categories", response_model=dict[str, list[dict[str, Any]]])
async def list_skill_templates_by_category() -> dict[str, list[dict[str, Any]]]:
    return get_templates_by_category()


@router.post(
    "/templates/{template_name}/install",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def install_skill_template(
    template_name: str,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SkillService, Depends(get_skill_service)],
) -> SkillResponse:
    tpl = next((t for t in SKILL_TEMPLATES if t["name"] == template_name), None)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
    s = await svc.create(
        user.id,
        tpl["name"],
        tpl["description"],
        tpl["skill_type"],
        tpl["source_code"],
        tpl.get("instructions"),
        tpl.get("parameters_schema", {}),
        tpl.get("permissions", []),
        tpl.get("is_public", False),
    )
    return SkillResponse.from_entity(s)


# ── Individual skill routes ──


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
        body.skill_type,
        body.source_code,
        body.instructions,
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
