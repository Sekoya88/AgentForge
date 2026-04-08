from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.workspace_member import WorkspaceMember
from app.infrastructure.persistence.postgres.models import WorkspaceMemberModel


class PostgresWorkspaceMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(m: WorkspaceMemberModel) -> WorkspaceMember:
        return WorkspaceMember(
            id=m.id,
            workspace_owner_id=m.workspace_owner_id,
            member_user_id=m.member_user_id,
            invited_email=m.invited_email,
            role=m.role,
            accepted_at=m.accepted_at,
            created_at=m.created_at,
        )

    async def invite(
        self,
        workspace_owner_id: UUID,
        invited_email: str,
        role: str,
        *,
        member_user_id: UUID | None = None,
    ) -> WorkspaceMember:
        m = WorkspaceMemberModel(
            workspace_owner_id=workspace_owner_id,
            member_user_id=member_user_id,
            invited_email=invited_email.lower().strip(),
            role=role,
        )
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return self._to_entity(m)

    async def list_for_workspace(self, workspace_owner_id: UUID) -> list[WorkspaceMember]:
        q = await self._session.execute(
            select(WorkspaceMemberModel)
            .where(WorkspaceMemberModel.workspace_owner_id == workspace_owner_id)
            .order_by(WorkspaceMemberModel.created_at)
        )
        return [self._to_entity(r) for r in q.scalars().all()]

    async def get_by_id(self, member_id: UUID, workspace_owner_id: UUID) -> WorkspaceMember | None:
        m = await self._session.get(WorkspaceMemberModel, member_id)
        if m is None or m.workspace_owner_id != workspace_owner_id:
            return None
        return self._to_entity(m)

    async def update_role(self, member_id: UUID, workspace_owner_id: UUID, role: str) -> bool:
        m = await self._session.get(WorkspaceMemberModel, member_id)
        if m is None or m.workspace_owner_id != workspace_owner_id:
            return False
        m.role = role
        await self._session.flush()
        return True

    async def remove(self, member_id: UUID, workspace_owner_id: UUID) -> bool:
        m = await self._session.get(WorkspaceMemberModel, member_id)
        if m is None or m.workspace_owner_id != workspace_owner_id:
            return False
        await self._session.delete(m)
        await self._session.flush()
        return True

    async def get_role_for_user(
        self, workspace_owner_id: UUID, user_id: UUID, user_email: str
    ) -> str | None:
        """Return the role of *user_id* in *workspace_owner_id*'s workspace, or None."""
        if workspace_owner_id == user_id:
            return "owner"
        q = await self._session.execute(
            select(WorkspaceMemberModel).where(
                WorkspaceMemberModel.workspace_owner_id == workspace_owner_id,
                WorkspaceMemberModel.member_user_id == user_id,
            )
        )
        row = q.scalar_one_or_none()
        if row:
            return row.role
        # Also check by email for pending invitations that the user hasn't linked yet
        q2 = await self._session.execute(
            select(WorkspaceMemberModel).where(
                WorkspaceMemberModel.workspace_owner_id == workspace_owner_id,
                WorkspaceMemberModel.invited_email == user_email.lower(),
                WorkspaceMemberModel.member_user_id.is_(None),
            )
        )
        row2 = q2.scalar_one_or_none()
        if row2:
            # Auto-link the invitation to this user
            row2.member_user_id = user_id
            row2.accepted_at = datetime.now(UTC)
            await self._session.flush()
            return row2.role
        return None
