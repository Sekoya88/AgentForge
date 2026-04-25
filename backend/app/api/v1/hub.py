import secrets as _secrets
import uuid
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_session
from app.domain.entities.user import User
from app.infrastructure.persistence.postgres.models import AgentModel

router = APIRouter(prefix="/hub", tags=["hub"])


@router.get("/agents")
async def list_public_agents(
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Public endpoint — no auth required."""
    q = select(AgentModel).where(AgentModel.is_public == True)  # noqa: E712
    if search:
        q = q.where(AgentModel.name.ilike(f"%{search}%"))
    q = q.order_by(AgentModel.stars.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    agents = result.scalars().all()
    return {
        "agents": [
            {
                "id": str(a.id),
                "name": a.name,
                "description": a.description,
                "stars": a.stars,
                "security_score": a.security_score,
                "status": a.status,
                "graph_node_count": len(a.graph_definition.get("nodes", []))
                if a.graph_definition
                else 0,
            }
            for a in agents
        ],
        "total": len(agents),
    }


@router.post("/agents/{agent_id}/publish", status_code=status.HTTP_200_OK)
async def publish_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Publish an agent to the hub (set is_public = true)."""
    from app.domain.exceptions import AgentNotFoundError

    agent = await session.get(AgentModel, agent_id)
    if not agent or agent.user_id != user.id:
        raise AgentNotFoundError()
    agent.is_public = True
    await session.commit()
    return {"published": True, "agent_id": str(agent_id)}


@router.post("/agents/{agent_id}/unpublish", status_code=status.HTTP_200_OK)
async def unpublish_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    from app.domain.exceptions import AgentNotFoundError

    agent = await session.get(AgentModel, agent_id)
    if not agent or agent.user_id != user.id:
        raise AgentNotFoundError()
    agent.is_public = False
    await session.commit()
    return {"published": False, "agent_id": str(agent_id)}


@router.post("/agents/{agent_id}/star", status_code=status.HTTP_200_OK)
async def star_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    await session.execute(
        update(AgentModel).where(AgentModel.id == agent_id).values(stars=AgentModel.stars + 1)
    )
    await session.commit()
    return {"starred": True}


@router.post("/agents/{agent_id}/clone", status_code=status.HTTP_201_CREATED)
async def clone_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Clone a public agent into the user's workspace."""
    from app.domain.exceptions import AgentNotFoundError

    source = await session.get(AgentModel, agent_id)
    if not source or not source.is_public:
        raise AgentNotFoundError()
    clone = AgentModel(
        id=uuid.uuid4(),
        user_id=user.id,
        name=f"{source.name} (clone)",
        description=source.description,
        graph_definition=dict(source.graph_definition),
        model_config=dict(source.model_config),
        interrupt_config=dict(source.interrupt_config or {}),
        skills=list(source.skills or []),
        execution_policy=dict(source.execution_policy or {}),
        status="draft",
        is_public=False,
        inbound_webhook_secret=_secrets.token_urlsafe(32),
    )
    session.add(clone)
    await session.commit()
    return {"agent_id": str(clone.id), "name": clone.name}
