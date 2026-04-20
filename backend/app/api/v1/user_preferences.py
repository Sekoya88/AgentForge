from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

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


class UpdateUserPreferencesRequest(BaseModel):
    onboarding_completed: bool | None = None
    role: str | None = None
    experience_level: str | None = None
    primary_languages: list[str] | None = None
    use_cases: list[str] | None = None
    response_style: str | None = None
    custom_context: str | None = None


def _to_response(prefs) -> UserPreferencesResponse:
    return UserPreferencesResponse(
        onboarding_completed=prefs.onboarding_completed,
        role=prefs.role,
        experience_level=prefs.experience_level,
        primary_languages=prefs.primary_languages,
        use_cases=prefs.use_cases,
        response_style=prefs.response_style,
        custom_context=prefs.custom_context,
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
    return _to_response(prefs)
