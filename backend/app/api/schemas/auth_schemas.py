from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    collect_speech_examples: bool = False

    model_config = {"from_attributes": True}


class UserPreferencesPatch(BaseModel):
    collect_speech_examples: bool | None = None


class UserContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bio: str | None
    preferences: dict
    custom_data: dict
    updated_at: datetime | None = None


class UserContextUpdateRequest(BaseModel):
    bio: str | None = None
    preferences: dict = Field(default_factory=dict)
    custom_data: dict = Field(default_factory=dict)


class GoogleIntegrationStatusResponse(BaseModel):
    connected: bool
    scopes: list[str]
    has_gmail_read: bool
    has_gmail_send: bool
    has_calendar_read: bool
    has_calendar_events: bool
