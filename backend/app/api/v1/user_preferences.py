from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import get_current_user, get_user_preferences_service
from app.domain.entities.user import User

router = APIRouter(prefix="/user-preferences", tags=["user-preferences"])


class UserPreferencesResponse(BaseModel):
    onboarding_completed: bool
    role: str | None
    experience_level: str | None
    primary_languages: list[str]
    use_cases: list[str]
    response_style: str | None
    custom_context: str | None
    memory_enabled: bool
    memory_compaction_day: int
    memory_compaction_hour: int
    memory_last_compacted_at: str | None
    memory_next_run_at: str | None


class UpdateUserPreferencesRequest(BaseModel):
    onboarding_completed: bool | None = None
    role: str | None = None
    experience_level: str | None = None
    primary_languages: list[str] | None = None
    use_cases: list[str] | None = None
    response_style: str | None = None
    custom_context: str | None = None
    memory_enabled: bool | None = None
    memory_compaction_day: Annotated[int, Field(ge=0, le=6)] | None = None
    memory_compaction_hour: Annotated[int, Field(ge=0, le=23)] | None = None


def _to_response(prefs) -> UserPreferencesResponse:
    return UserPreferencesResponse(
        onboarding_completed=prefs.onboarding_completed,
        role=prefs.role,
        experience_level=prefs.experience_level,
        primary_languages=prefs.primary_languages,
        use_cases=prefs.use_cases,
        response_style=prefs.response_style,
        custom_context=prefs.custom_context,
        memory_enabled=prefs.memory_enabled,
        memory_compaction_day=prefs.memory_compaction_day,
        memory_compaction_hour=prefs.memory_compaction_hour,
        memory_last_compacted_at=prefs.memory_last_compacted_at.isoformat()
        if prefs.memory_last_compacted_at
        else None,
        memory_next_run_at=prefs.memory_next_run_at.isoformat()
        if prefs.memory_next_run_at
        else None,
    )


@router.get("", response_model=UserPreferencesResponse)
async def get_preferences(
    user: Annotated[User, Depends(get_current_user)],
    svc=Depends(get_user_preferences_service),
):
    prefs = await svc.get_or_create(user.id)
    return _to_response(prefs)


@router.put("", response_model=UserPreferencesResponse)
async def update_preferences(
    body: UpdateUserPreferencesRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc=Depends(get_user_preferences_service),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    prefs = await svc.update(user.id, **updates)
    if body.memory_compaction_day is not None or body.memory_compaction_hour is not None:
        next_run = svc.next_run_at(prefs)
        prefs = await svc.update(user.id, memory_next_run_at=next_run)
    return _to_response(prefs)
