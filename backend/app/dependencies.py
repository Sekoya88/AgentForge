from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.agent_service import AgentService
from app.application.services.auth_service import AuthService
from app.application.services.campaign_service import CampaignService
from app.application.services.finetune_service import FinetuneService
from app.application.services.sandbox_service import SandboxService
from app.application.services.skill_service import SkillService
from app.config import Settings, get_settings
from app.domain.entities.user import User
from app.domain.ports.agent_orchestrator import AgentOrchestrator
from app.domain.ports.agent_repository import AgentRepository
from app.domain.ports.campaign_repository import CampaignRepository
from app.domain.ports.finetune_repository import FinetuneJobRepository
from app.domain.ports.skill_repository import SkillRepository
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.auth.jwt_handler import decode_token
from app.infrastructure.orchestration.langgraph_orchestrator import LangGraphAgentOrchestrator
from app.infrastructure.persistence.postgres.agent_repo import PostgresAgentRepository
from app.infrastructure.persistence.postgres.campaign_repo import PostgresCampaignRepository
from app.infrastructure.persistence.postgres.finetune_repo import PostgresFinetuneJobRepository
from app.infrastructure.persistence.postgres.session import get_session_factory
from app.infrastructure.persistence.postgres.skill_repo import PostgresSkillRepository
from app.infrastructure.persistence.postgres.user_repo import PostgresUserRepository
from app.infrastructure.redis_client import get_redis_client
from app.infrastructure.redteam.factory import redteam_engine_from_settings
from app.infrastructure.sandbox.subprocess_sandbox import SubprocessSandboxRuntime

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep() -> Settings:
    return get_settings()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepository:
    return PostgresUserRepository(session)


def get_agent_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRepository:
    return PostgresAgentRepository(session)


def get_campaign_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CampaignRepository:
    return PostgresCampaignRepository(session)


def get_skill_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SkillRepository:
    return PostgresSkillRepository(session)


def get_finetune_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FinetuneJobRepository:
    return PostgresFinetuneJobRepository(session)


def get_orchestrator(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> AgentOrchestrator:
    return LangGraphAgentOrchestrator(settings=settings)


def get_redis_optional() -> redis.Redis | None:
    return get_redis_client()


def get_redis_required(
    r: Annotated[redis.Redis | None, Depends(get_redis_optional)],
) -> redis.Redis:
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis unavailable",
        )
    return r


def get_auth_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> AuthService:
    return AuthService(users, settings)


def get_agent_service(
    repo: Annotated[AgentRepository, Depends(get_agent_repository)],
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
    redis_client: Annotated[redis.Redis | None, Depends(get_redis_optional)],
) -> AgentService:
    return AgentService(repo, orchestrator, redis_client)


def get_campaign_service(
    campaigns: Annotated[CampaignRepository, Depends(get_campaign_repository)],
    agents: Annotated[AgentRepository, Depends(get_agent_repository)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> CampaignService:
    return CampaignService(campaigns, agents, redteam_engine_from_settings(settings))


def get_skill_service(
    repo: Annotated[SkillRepository, Depends(get_skill_repository)],
) -> SkillService:
    return SkillService(repo)


def get_finetune_service(
    repo: Annotated[FinetuneJobRepository, Depends(get_finetune_repository)],
) -> FinetuneService:
    return FinetuneService(repo)


def get_sandbox_service(
    redis_client: Annotated[redis.Redis | None, Depends(get_redis_optional)],
) -> SandboxService:
    return SandboxService(SubprocessSandboxRuntime(), redis_client)


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        uid = decode_token(creds.credentials, settings, expect_typ="access")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None
    repo = PostgresUserRepository(session)
    user = await repo.get_by_id(uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
