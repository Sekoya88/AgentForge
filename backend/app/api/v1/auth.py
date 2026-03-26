from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.api.middleware.rate_limit import limiter
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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/register", response_model=UserResponse)
@limiter.limit("10/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    return await svc.register(body.email, body.password, body.display_name)


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


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await svc.change_password(user.id, body.current_password, body.new_password)
