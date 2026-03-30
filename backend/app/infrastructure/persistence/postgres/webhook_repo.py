from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.models import WebhookSubscriptionModel


@dataclass(frozen=True, slots=True)
class WebhookEndpoint:
    id: UUID
    url: str
    secret: str | None


class PostgresWebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: UUID,
        url: str,
        events: list[str],
        secret: str | None,
    ) -> WebhookSubscriptionModel:
        m = WebhookSubscriptionModel(
            user_id=user_id,
            url=url,
            events=list(events),
            secret=secret,
            active=True,
        )
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return m

    async def list_for_user(self, user_id: UUID) -> list[WebhookSubscriptionModel]:
        q = await self._session.execute(
            select(WebhookSubscriptionModel)
            .where(WebhookSubscriptionModel.user_id == user_id)
            .order_by(WebhookSubscriptionModel.created_at.desc())
        )
        return list(q.scalars().all())

    async def delete(self, webhook_id: UUID, user_id: UUID) -> bool:
        q = await self._session.execute(
            select(WebhookSubscriptionModel).where(
                WebhookSubscriptionModel.id == webhook_id,
                WebhookSubscriptionModel.user_id == user_id,
            )
        )
        m = q.scalar_one_or_none()
        if m is None:
            return False
        await self._session.delete(m)
        return True

    async def list_active_for_user_event(self, user_id: UUID, event: str) -> list[WebhookEndpoint]:
        q = await self._session.execute(
            select(WebhookSubscriptionModel).where(
                WebhookSubscriptionModel.user_id == user_id,
                WebhookSubscriptionModel.active.is_(True),
            )
        )
        out: list[WebhookEndpoint] = []
        for m in q.scalars().all():
            ev: Any = m.events
            if not isinstance(ev, list):
                continue
            if event in ev:
                out.append(self._to_ep(m))
        return out

    @staticmethod
    def _to_ep(m: WebhookSubscriptionModel) -> WebhookEndpoint:
        return WebhookEndpoint(id=m.id, url=m.url, secret=m.secret)
