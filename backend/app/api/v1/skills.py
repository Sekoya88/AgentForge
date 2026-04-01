from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.skill_schemas import (
    SkillCreateRequest,
    SkillRegistryItemResponse,
    SkillResponse,
    SkillUpdateRequest,
    SkillValidateResponse,
)
from app.application.services.skill_service import SkillService
from app.dependencies import get_current_user, get_session, get_skill_service
from app.domain.entities.user import User
from app.domain.skill_templates import SKILL_TEMPLATES, get_templates_by_category
from app.infrastructure.persistence.postgres.models import SkillModel

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


@router.get("/registry", response_model=list[SkillRegistryItemResponse])
async def list_public_skill_registry(
    svc: Annotated[SkillService, Depends(get_skill_service)],
    search: Annotated[str | None, Query(description="Filter by name or description")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SkillRegistryItemResponse]:
    rows = await svc.list_public_registry(search, limit=limit)
    return [SkillRegistryItemResponse.from_skill(s, author) for s, author in rows]


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


@router.post("/seed-defaults", status_code=201)
async def seed_default_skills(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Install default skill templates for the current user if not already present."""
    created = []
    for tpl in SKILL_TEMPLATES:
        existing = await db.execute(
            select(SkillModel).where(
                SkillModel.user_id == current_user.id,
                SkillModel.name == tpl["name"],
            )
        )
        if existing.scalars().first():
            continue
        skill = SkillModel(
            id=uuid4(),
            user_id=current_user.id,
            name=tpl["name"],
            description=tpl.get("description", ""),
            skill_type=tpl["skill_type"],
            source_code=tpl.get("source_code", ""),
            instructions=tpl.get("instructions"),
            parameters_schema=tpl.get("parameters_schema", {}),
            permissions=tpl.get("permissions", []),
            is_public=False,
            security_validated=True,
        )
        db.add(skill)
        created.append(tpl["name"])
    await db.commit()
    return {"created": created, "count": len(created)}


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
