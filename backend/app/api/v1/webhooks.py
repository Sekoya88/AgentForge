from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.webhook_schemas import WebhookCreateRequest, WebhookResponse
from app.dependencies import get_current_user, get_session
from app.domain.entities.user import User
from app.infrastructure.persistence.postgres.webhook_repo import PostgresWebhookRepository

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_ALLOWED = frozenset({"execution.completed", "campaign.completed"})


def _get_repo(session: AsyncSession) -> PostgresWebhookRepository:
    return PostgresWebhookRepository(session)


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WebhookResponse:
    evs = list(body.events)
    bad = [e for e in evs if e not in _ALLOWED]
    if bad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown event(s): {bad}. Allowed: {sorted(_ALLOWED)}",
        )
    repo = _get_repo(session)
    m = await repo.create(
        user.id,
        str(body.url),
        evs,
        body.secret,
    )
    return WebhookResponse(
        id=m.id,
        url=m.url,
        events=list(m.events) if isinstance(m.events, list) else [],
        active=m.active,
        created_at=m.created_at,
    )


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WebhookResponse]:
    repo = _get_repo(session)
    rows = await repo.list_for_user(user.id)
    return [
        WebhookResponse(
            id=m.id,
            url=m.url,
            events=list(m.events) if isinstance(m.events, list) else [],
            active=m.active,
            created_at=m.created_at,
        )
        for m in rows
    ]


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    repo = _get_repo(session)
    ok = await repo.delete(webhook_id, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
