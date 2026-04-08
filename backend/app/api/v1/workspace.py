"""Workspace permissions — invite members with owner / editor / viewer roles.

Each user's "workspace" is the collection of agents they own.  By inviting
other users, the workspace owner grants them scoped access.

Roles
-----
owner  – implicit for the agent owner; full CRUD
editor – read, run, and update agents; cannot delete
viewer – read and run agents only; cannot modify
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator

from app.dependencies import get_current_user, get_workspace_member_repository
from app.domain.entities.user import User
from app.domain.entities.workspace_member import WorkspaceMember
from app.infrastructure.persistence.postgres.workspace_member_repo import (
    PostgresWorkspaceMemberRepository,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])

_MUTABLE_ROLES = frozenset({"editor", "viewer"})


# ── Schemas ──────────────────────────────────────────────────────────────────


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in _MUTABLE_ROLES:
            raise ValueError(f"role must be one of {sorted(_MUTABLE_ROLES)}")
        return v


class UpdateRoleRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in _MUTABLE_ROLES:
            raise ValueError(f"role must be one of {sorted(_MUTABLE_ROLES)}")
        return v


class WorkspaceMemberResponse(BaseModel):
    id: UUID
    invited_email: str
    role: str
    accepted: bool

    @classmethod
    def from_entity(cls, m: WorkspaceMember) -> WorkspaceMemberResponse:
        return cls(
            id=m.id,
            invited_email=m.invited_email,
            role=m.role,
            accepted=m.accepted_at is not None,
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/members", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED
)
async def invite_member(
    body: InviteMemberRequest,
    user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[PostgresWorkspaceMemberRepository, Depends(get_workspace_member_repository)],
) -> WorkspaceMemberResponse:
    """Invite a user by email to your workspace."""
    existing = await repo.list_for_workspace(user.id)
    if any(m.invited_email == body.email.lower() for m in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email already has a pending or accepted invitation.",
        )
    member = await repo.invite(user.id, body.email, body.role)
    return WorkspaceMemberResponse.from_entity(member)


@router.get("/members", response_model=list[WorkspaceMemberResponse])
async def list_members(
    user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[PostgresWorkspaceMemberRepository, Depends(get_workspace_member_repository)],
) -> list[WorkspaceMemberResponse]:
    """List all members (pending or accepted) in your workspace."""
    members = await repo.list_for_workspace(user.id)
    return [WorkspaceMemberResponse.from_entity(m) for m in members]


@router.put("/members/{member_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    member_id: UUID,
    body: UpdateRoleRequest,
    user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[PostgresWorkspaceMemberRepository, Depends(get_workspace_member_repository)],
) -> WorkspaceMemberResponse:
    """Change the role of an existing member."""
    ok = await repo.update_role(member_id, user.id, body.role)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    member = await repo.get_by_id(member_id, user.id)
    return WorkspaceMemberResponse.from_entity(member)  # type: ignore[arg-type]


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[PostgresWorkspaceMemberRepository, Depends(get_workspace_member_repository)],
) -> None:
    """Remove a member from your workspace."""
    ok = await repo.remove(member_id, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")


@router.get("/my-role/{workspace_owner_id}")
async def my_role_in_workspace(
    workspace_owner_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[PostgresWorkspaceMemberRepository, Depends(get_workspace_member_repository)],
) -> dict:
    """Return the current user's role in another user's workspace."""
    role = await repo.get_role_for_user(workspace_owner_id, user.id, user.email)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access")
    return {"role": role}
