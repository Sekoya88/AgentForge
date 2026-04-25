from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class WebhookCreateRequest(BaseModel):
    url: HttpUrl
    events: list[str] = Field(
        default_factory=lambda: ["execution.completed"],
        description="Subset of: execution.completed, campaign.completed",
    )
    secret: str | None = Field(
        default=None,
        max_length=512,
        description="Optional HMAC-SHA256 secret for X-AgentForge-Signature header",
    )


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    events: list[str]
    active: bool
    created_at: datetime
