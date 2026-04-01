from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.rate_limit import limiter
from app.api.schemas.auth_schemas import (
    GoogleIntegrationStatusResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserContextResponse,
    UserContextUpdateRequest,
    UserPreferencesPatch,
    UserResponse,
)
from app.application.services.agent_service import AgentService
from app.application.services.auth_service import AuthService
from app.application.services.google_oauth_service import GoogleOAuthService
from app.application.services.skill_service import SkillService
from app.config import Settings
from app.dependencies import (
    get_agent_service,
    get_auth_service,
    get_current_user,
    get_session,
    get_settings_dep,
    get_skill_service,
)
from app.domain.default_agents import seed_default_agents
from app.domain.entities.user import User
from app.infrastructure.auth.google_oauth_flow import (
    SCOPE_CALENDAR_EVENTS,
    SCOPE_CALENDAR_READONLY,
    SCOPE_GMAIL_READONLY,
    SCOPE_GMAIL_SEND,
)
from app.infrastructure.auth.jwt_handler import create_sdk_token
from app.infrastructure.persistence.postgres.models import SocialAccountModel, UserContextModel
from app.infrastructure.persistence.postgres.social_account_repo import (
    PostgresSocialAccountRepository,
)
from app.infrastructure.persistence.postgres.user_repo import PostgresUserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.get("/oauth/google")
@limiter.limit("30/minute")
async def google_oauth_start(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> RedirectResponse:
    from app.infrastructure.auth.google_oauth_flow import build_authorize_url

    if not settings.google_oauth_client_id or not settings.google_oauth_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )
    try:
        url = build_authorize_url(settings)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/oauth/google/callback")
@limiter.limit("60/minute")
async def google_oauth_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    session: Annotated[AsyncSession, Depends(get_session)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    base = settings.oauth_frontend_redirect_url.rstrip("/")
    if error:
        return RedirectResponse(url=f"{base}?oauth_error={quote(error)}")
    if not code or not state:
        return RedirectResponse(url=f"{base}?oauth_error=missing_params")
    try:
        svc = GoogleOAuthService(
            settings,
            PostgresUserRepository(session),
            PostgresSocialAccountRepository(session),
        )
        access, refresh, _ = await svc.complete_google_login(code, state)
    except ValueError as e:
        return RedirectResponse(url=f"{base}?oauth_error={quote(str(e))}")
    except Exception:
        return RedirectResponse(url=f"{base}?oauth_error=server_error")
    frag = f"access_token={quote(access, safe='')}&refresh_token={quote(refresh, safe='')}"
    return RedirectResponse(url=f"{base}#{frag}", status_code=status.HTTP_302_FOUND)


@router.post("/register", response_model=UserResponse)
@limiter.limit("10/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    svc: Annotated[AuthService, Depends(get_auth_service)],
    agent_svc: Annotated[AgentService, Depends(get_agent_service)],
    skill_svc: Annotated[SkillService, Depends(get_skill_service)],
) -> User:
    user = await svc.register(body.email, body.password, body.display_name)
    await seed_default_agents(user.id, agent_svc, skill_svc)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    access, refresh, _ = await svc.login(body.email, body.password)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    access = svc.refresh(body.refresh_token)
    return TokenResponse(access_token=access, refresh_token=body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.get("/me/token")
async def get_api_token(
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict:
    """Return a long-lived token (365 days) for SDK usage. Authenticate via the web UI first."""
    token = create_sdk_token(current_user.id, settings)
    return {
        "api_key": token,
        "note": "Store this securely. Use as Bearer token in the AgentForge SDK.",
    }


@router.patch("/me", response_model=UserResponse)
async def patch_me(
    body: UserPreferencesPatch,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    try:
        return await svc.patch_preferences(
            user.id, collect_speech_examples=body.collect_speech_examples
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await svc.change_password(user.id, body.current_password, body.new_password)


@router.get("/me/context", response_model=UserContextResponse)
async def get_user_context(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserContextResponse:
    result = await db.execute(
        select(UserContextModel).where(UserContextModel.user_id == current_user.id)
    )
    ctx = result.scalar_one_or_none()
    if ctx is None:
        return UserContextResponse(bio=None, preferences={}, custom_data={})
    return UserContextResponse.model_validate(ctx)


@router.put("/me/context", response_model=UserContextResponse)
async def update_user_context(
    body: UserContextUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserContextResponse:
    result = await db.execute(
        select(UserContextModel).where(UserContextModel.user_id == current_user.id)
    )
    ctx = result.scalar_one_or_none()
    if ctx:
        ctx.bio = body.bio
        ctx.preferences = body.preferences
        ctx.custom_data = body.custom_data
        ctx.updated_at = datetime.utcnow()
    else:
        ctx = UserContextModel(
            user_id=current_user.id,
            bio=body.bio,
            preferences=body.preferences,
            custom_data=body.custom_data,
            updated_at=datetime.utcnow(),
        )
        db.add(ctx)
    await db.commit()
    await db.refresh(ctx)
    return UserContextResponse.model_validate(ctx)


@router.get("/me/google-status", response_model=GoogleIntegrationStatusResponse)
async def google_integration_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> GoogleIntegrationStatusResponse:
    result = await db.execute(
        select(SocialAccountModel).where(
            SocialAccountModel.user_id == current_user.id,
            SocialAccountModel.provider == "google",
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return GoogleIntegrationStatusResponse(
            connected=False,
            scopes=[],
            has_gmail_read=False,
            has_gmail_send=False,
            has_calendar_read=False,
            has_calendar_events=False,
        )
    scopes = list(row.scopes or [])
    return GoogleIntegrationStatusResponse(
        connected=True,
        scopes=scopes,
        has_gmail_read=SCOPE_GMAIL_READONLY in scopes,
        has_gmail_send=SCOPE_GMAIL_SEND in scopes,
        has_calendar_read=SCOPE_CALENDAR_READONLY in scopes,
        has_calendar_events=SCOPE_CALENDAR_EVENTS in scopes,
    )
