"""Seed the local DB with a demo user, skill, and agent.

Idempotent: skips rows that already exist (matched by email / name).

Usage:
    cd backend && uv run python ../scripts/seed.py
    # or: make seed
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.infrastructure.persistence.postgres.models import (  # noqa: E402
    AgentModel,
    SkillModel,
    UserModel,
)

DEMO_EMAIL = "demo@agentforge.dev"
DEMO_PASSWORD = "agentforge"
DEMO_DISPLAY = "Demo User"

SKILL_NAME = "uppercase"
SKILL_SOURCE = 'def run(x: str) -> str:\n    """Return the input uppercased."""\n    return x.upper()\n'

AGENT_NAME = "Echo Agent"
AGENT_DESCRIPTION = "Demo agent: sends user input through the uppercase skill."
AGENT_GRAPH = {
    "nodes": [
        {"id": "t1", "type": "tool", "config": {"tool_name": SKILL_NAME}},
    ],
    "edges": [],
    "entry_point": "t1",
}
AGENT_MODEL_CONFIG = {"provider": "mock", "model": "echo"}


def _load_env() -> None:
    env_path = _REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


async def seed(session: AsyncSession) -> None:
    # --- user ---
    row = (await session.execute(select(UserModel).where(UserModel.email == DEMO_EMAIL))).scalar_one_or_none()
    if row:
        user_id = row.id
        print(f"  user  {DEMO_EMAIL} already exists ({user_id})")
    else:
        user = UserModel(
            email=DEMO_EMAIL,
            hashed_password=_hash_password(DEMO_PASSWORD),
            display_name=DEMO_DISPLAY,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        user_id = user.id
        print(f"  user  {DEMO_EMAIL} created ({user_id})")

    # --- skill ---
    row = (
        await session.execute(
            select(SkillModel).where(SkillModel.user_id == user_id, SkillModel.name == SKILL_NAME)
        )
    ).scalar_one_or_none()
    if row:
        skill_id = row.id
        print(f"  skill {SKILL_NAME} already exists ({skill_id})")
    else:
        skill = SkillModel(
            user_id=user_id,
            name=SKILL_NAME,
            description="Returns the input string in UPPERCASE.",
            version="1.0.0",
            source_code=SKILL_SOURCE,
            parameters_schema={},
            permissions=[],
            is_public=False,
            security_validated=True,
        )
        session.add(skill)
        await session.flush()
        await session.refresh(skill)
        skill_id = skill.id
        print(f"  skill {SKILL_NAME} created ({skill_id})")

    # --- agent ---
    row = (
        await session.execute(
            select(AgentModel).where(AgentModel.user_id == user_id, AgentModel.name == AGENT_NAME)
        )
    ).scalar_one_or_none()
    if row:
        print(f"  agent {AGENT_NAME} already exists ({row.id})")
    else:
        agent = AgentModel(
            user_id=user_id,
            name=AGENT_NAME,
            description=AGENT_DESCRIPTION,
            graph_definition=AGENT_GRAPH,
            model_config=AGENT_MODEL_CONFIG,
            interrupt_config={},
            skills=[str(skill_id)],
            status="active",
        )
        session.add(agent)
        await session.flush()
        await session.refresh(agent)
        print(f"  agent {AGENT_NAME} created ({agent.id})")

    await session.commit()


async def main() -> None:
    _load_env()
    url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://forge:forge@localhost:5433/agentforge")
    print(f"Seeding → {url.split('@')[1] if '@' in url else url}")

    engine = create_async_engine(url, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed(session)

    await engine.dispose()

    print()
    print("Done. Login credentials:")
    print(f"  email:    {DEMO_EMAIL}")
    print(f"  password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
