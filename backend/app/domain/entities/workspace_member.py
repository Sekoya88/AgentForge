from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

ROLES = frozenset({"owner", "editor", "viewer"})


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    """A user invited into another user's workspace with a given role.

    Workspace = the collection of agents owned by ``workspace_owner_id``.
    Roles:
      owner  – full CRUD (implicit for the owning user, not stored in DB)
      editor – can read, run, and modify agents
      viewer – can read and run agents only
    """

    id: UUID
    workspace_owner_id: UUID
    member_user_id: UUID | None
    invited_email: str
    role: str
    accepted_at: datetime | None
    created_at: datetime
