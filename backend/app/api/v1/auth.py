from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.schemas.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.application.services.auth_service import AuthService
from app.dependencies import get_auth_service, get_current_user
from app.domain.entities.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register(
    body: RegisterRequest,
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    return await svc.register(body.email, body.password, body.display_name)


@router.post("/login", response_model=TokenResponse)
async def login(
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
