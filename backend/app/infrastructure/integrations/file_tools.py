"""Sandboxed file read/write tools for the Forge assistant.

All paths are confined to ``FORGE_WORKSPACE_ROOT / {user_id}`` to prevent
arbitrary filesystem access.  Symlinks escaping the sandbox are rejected.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

# Root workspace — all forge file ops happen under here
FORGE_WORKSPACE_ROOT = Path(__file__).resolve().parents[3] / "forge_workspace"


def _user_root(user_id: UUID) -> Path:
    root = FORGE_WORKSPACE_ROOT / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(user_id: UUID, rel_path: str) -> Path:
    """Resolve *rel_path* under user sandbox.  Raises ValueError on escape."""
    root = _user_root(user_id)
    # Normalise, resolve, and confirm it stays inside sandbox
    candidate = (root / rel_path).resolve()
    if not str(candidate).startswith(str(root)):
        raise ValueError(f"Path escapes sandbox: {rel_path!r}")
    return candidate


async def read_file(user_id: UUID, path: str) -> dict:
    """Read a file from the user's Forge workspace.

    Returns ``{path, content, size_bytes}`` or ``{error}``.
    """
    try:
        target = _safe_path(user_id, path)
    except ValueError as e:
        return {"error": str(e)}

    if not target.is_file():
        # List directory if it's a dir
        if target.is_dir():
            entries = sorted(os.listdir(target))[:50]
            return {
                "path": str(target.relative_to(FORGE_WORKSPACE_ROOT)),
                "type": "directory",
                "entries": entries,
            }
        return {"error": f"File not found: {path}"}

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        # Cap at 50KB to avoid overwhelming the LLM context
        truncated = len(content) > 50_000
        if truncated:
            content = content[:50_000] + "\n\n... [truncated — file exceeds 50KB]"
        return {
            "path": str(target.relative_to(FORGE_WORKSPACE_ROOT)),
            "content": content,
            "size_bytes": target.stat().st_size,
            "truncated": truncated,
        }
    except Exception as e:
        return {"error": f"Cannot read {path}: {e}"}


async def write_file(user_id: UUID, path: str, content: str) -> dict:
    """Write a file to the user's Forge workspace.

    Creates parent directories as needed.  Returns ``{path, size_bytes}`` or ``{error}``.
    """
    try:
        target = _safe_path(user_id, path)
    except ValueError as e:
        return {"error": str(e)}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "path": str(target.relative_to(FORGE_WORKSPACE_ROOT)),
            "size_bytes": target.stat().st_size,
            "message": f"File written successfully: {path}",
        }
    except Exception as e:
        return {"error": f"Cannot write {path}: {e}"}


async def list_workspace(user_id: UUID) -> dict:
    """List the contents of the user's Forge workspace root."""
    root = _user_root(user_id)
    entries = []
    for item in sorted(root.rglob("*")):
        if len(entries) >= 100:
            break
        rel = item.relative_to(root)
        entries.append(
            {
                "path": str(rel),
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            }
        )
    return {"workspace": str(root), "entries": entries}
