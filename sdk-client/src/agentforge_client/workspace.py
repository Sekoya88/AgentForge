"""Workspace member management — `/api/v1/workspace`."""

from __future__ import annotations

from typing import Any

import httpx


class WorkspaceAPI:
    """Use via ``client.workspace``."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list_members(self) -> list[dict[str, Any]]:
        """List all members of the current user's workspace."""
        r = await self._client.get("/api/v1/workspace/members")
        r.raise_for_status()
        return r.json()

    async def invite(self, email: str, role: str = "viewer") -> dict[str, Any]:
        """Invite a user to the workspace by email. role: owner|editor|viewer."""
        r = await self._client.post("/api/v1/workspace/members", json={"email": email, "role": role})
        r.raise_for_status()
        return r.json()

    async def update_role(self, member_id: str, role: str) -> dict[str, Any]:
        """Update the role of an existing workspace member."""
        r = await self._client.put(f"/api/v1/workspace/members/{member_id}", json={"role": role})
        r.raise_for_status()
        return r.json()

    async def remove(self, member_id: str) -> None:
        """Remove a member from the workspace."""
        r = await self._client.delete(f"/api/v1/workspace/members/{member_id}")
        r.raise_for_status()

    async def my_role(self, workspace_owner_id: str) -> dict[str, Any]:
        """Get the current user's role in a specific workspace."""
        r = await self._client.get(f"/api/v1/workspace/my-role/{workspace_owner_id}")
        r.raise_for_status()
        return r.json()
