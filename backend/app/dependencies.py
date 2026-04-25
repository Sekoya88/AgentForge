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
from app.application.services.knowledge_service import KnowledgeService
from app.application.services.sandbox_service import SandboxService
from app.application.services.secrets_service import SecretsService
from app.application.services.skill_service import SkillService
from app.application.services.user_preferences_service import UserPreferencesService
from app.config import Settings, get_settings
from app.domain.entities.user import User
from app.domain.ports.agent_orchestrator import AgentOrchestrator
from app.domain.ports.agent_repository import AgentRepository
from app.domain.ports.campaign_repository import CampaignRepository
from app.domain.ports.finetune_repository import FinetuneJobRepository
from app.domain.ports.skill_repository import SkillRepository
from app.domain.ports.user_preferences_repository import UserPreferencesRepository
from app.domain.ports.user_repository import UserRepository
from app.domain.ports.user_secrets_repository import UserSecretsRepository
from app.infrastructure.auth.jwt_handler import decode_token
from app.infrastructure.orchestration.langgraph_orchestrator import LangGraphAgentOrchestrator
from app.infrastructure.persistence.postgres.agent_repo import PostgresAgentRepository
from app.infrastructure.persistence.postgres.campaign_repo import PostgresCampaignRepository
from app.infrastructure.persistence.postgres.finetune_repo import PostgresFinetuneJobRepository
from app.infrastructure.persistence.postgres.knowledge_repo import PostgresKnowledgeRepository
from app.infrastructure.persistence.postgres.session import get_session_factory
from app.infrastructure.persistence.postgres.skill_repo import PostgresSkillRepository
from app.infrastructure.persistence.postgres.speech_example_repo import (
    PostgresSpeechExampleRepository,
)
from app.infrastructure.persistence.postgres.user_preferences_repo import (
    PostgresUserPreferencesRepository,
)
from app.infrastructure.persistence.postgres.user_repo import PostgresUserRepository
from app.infrastructure.persistence.postgres.user_secrets_repo import PostgresUserSecretsRepository
from app.infrastructure.persistence.postgres.voice_sample_repo import PostgresVoiceSampleRepository
from app.infrastructure.persistence.postgres.workspace_member_repo import (
    PostgresWorkspaceMemberRepository,
)
from app.infrastructure.redis_client import get_redis_client
from app.infrastructure.redteam.factory import redteam_engine_from_settings
from app.infrastructure.sandbox.docker_sandbox import DockerSandboxRuntime
from app.infrastructure.sandbox.subprocess_sandbox import SubprocessSandboxRuntime
from app.infrastructure.storage.s3_store import S3AudioStore

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


def get_user_secrets_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserSecretsRepository:
    return PostgresUserSecretsRepository(session)


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


def get_voice_sample_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PostgresVoiceSampleRepository:
    return PostgresVoiceSampleRepository(session)


def get_speech_example_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PostgresSpeechExampleRepository:
    return PostgresSpeechExampleRepository(session)


def get_workspace_member_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PostgresWorkspaceMemberRepository:
    return PostgresWorkspaceMemberRepository(session)


def get_s3_audio_store(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> S3AudioStore:
    return S3AudioStore(settings)


def get_secrets_service(
    repo: Annotated[UserSecretsRepository, Depends(get_user_secrets_repository)],
) -> SecretsService:
    return SecretsService(repo)


def get_knowledge_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    secrets: Annotated[SecretsService, Depends(get_secrets_service)],
) -> KnowledgeService:
    return KnowledgeService(PostgresKnowledgeRepository(session), settings, secrets)


def _build_sandbox_runtime(settings: Settings):
    if settings.sandbox_mode.lower() == "docker":
        return DockerSandboxRuntime()
    return SubprocessSandboxRuntime()


def build_sandbox_runtime(settings: Settings):
    """Public factory for sandbox runtime (tests, tooling)."""
    return _build_sandbox_runtime(settings)


def get_orchestrator(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> AgentOrchestrator:
    return LangGraphAgentOrchestrator(
        settings=settings,
        sandbox=_build_sandbox_runtime(settings),
    )


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
    skills: Annotated[SkillRepository, Depends(get_skill_repository)],
    finetune: Annotated[FinetuneJobRepository, Depends(get_finetune_repository)],
    redis_client: Annotated[redis.Redis | None, Depends(get_redis_optional)],
    knowledge: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    secrets: Annotated[SecretsService, Depends(get_secrets_service)],
    campaigns: Annotated[CampaignRepository, Depends(get_campaign_repository)],
    speech_examples: Annotated[
        PostgresSpeechExampleRepository, Depends(get_speech_example_repository)
    ],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    s3: Annotated[S3AudioStore, Depends(get_s3_audio_store)],
) -> AgentService:
    return AgentService(
        repo=repo,
        orchestrator=orchestrator,
        skill_repo=skills,
        finetune_repo=finetune,
        redis_client=redis_client,
        knowledge_service=knowledge,
        secrets_service=secrets,
        campaign_repo=campaigns,
        speech_example_repo=speech_examples,
        user_repo=users,
        s3_audio_store=s3,
    )


def build_agent_service_for_worker(session: AsyncSession) -> AgentService:
    """Construct AgentService with repos bound to one session (background worker)."""
    settings = get_settings()
    secrets = SecretsService(PostgresUserSecretsRepository(session))
    return AgentService(
        repo=PostgresAgentRepository(session),
        orchestrator=LangGraphAgentOrchestrator(
            settings=settings,
            sandbox=_build_sandbox_runtime(settings),
        ),
        skill_repo=PostgresSkillRepository(session),
        finetune_repo=PostgresFinetuneJobRepository(session),
        redis_client=get_redis_client(),
        knowledge_service=KnowledgeService(
            PostgresKnowledgeRepository(session),
            settings,
            secrets,
        ),
        secrets_service=secrets,
        campaign_repo=PostgresCampaignRepository(session),
        speech_example_repo=PostgresSpeechExampleRepository(session),
        user_repo=PostgresUserRepository(session),
        s3_audio_store=S3AudioStore(settings),
    )


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
    settings: Annotated[Settings, Depends(get_settings_dep)],
    redis_client: Annotated[redis.Redis | None, Depends(get_redis_optional)],
) -> FinetuneService:
    return FinetuneService(repo, settings, redis_client)


def get_sandbox_service(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    redis_client: Annotated[redis.Redis | None, Depends(get_redis_optional)],
) -> SandboxService:
    return SandboxService(_build_sandbox_runtime(settings), redis_client)


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


async def get_forge_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    r: Annotated[redis.Redis, Depends(get_redis_required)],
    user: Annotated[User, Depends(get_current_user)],
    secrets_svc: Annotated[SecretsService, Depends(get_secrets_service)],
):
    from app.application.services.forge_memory_service import ForgeMemoryService
    from app.application.services.forge_service import ForgeService
    from app.infrastructure.persistence.postgres.forge_memory_repo import (
        PostgresForgeMemoryRepository,
    )
    from app.infrastructure.persistence.postgres.forge_repos import (
        ForgeConversationRepo,
        ForgeExecutionRepo,
    )

    settings = get_settings()
    secrets = await secrets_svc.get_decrypted_secrets(user.id)

    openai_key = secrets.get("openai_key") or settings.openai_api_key or None
    google_key = secrets.get("google_key") or settings.google_api_key or None
    anthropic_key = secrets.get("anthropic_key") or settings.anthropic_api_key or None
    tavily_key = secrets.get("tavily_key") or settings.tavily_api_key or None
    hf_token = secrets.get("hf_token") or settings.hf_token or None

    memory_repo = PostgresForgeMemoryRepository(session)
    memory_svc = ForgeMemoryService(memory_repo, session)

    return ForgeService(
        conv_repo=ForgeConversationRepo(session),
        exec_repo=ForgeExecutionRepo(session),
        redis_client=r,
        db_factory=get_session_factory(),
        openai_key=openai_key,
        google_key=google_key,
        anthropic_key=anthropic_key,
        tavily_key=tavily_key,
        hf_token=hf_token,
        user_id=user.id,
        memory_svc=memory_svc,
    )


def get_user_preferences_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserPreferencesRepository:
    return PostgresUserPreferencesRepository(session)


def get_user_preferences_service(
    repo: Annotated[UserPreferencesRepository, Depends(get_user_preferences_repository)],
) -> UserPreferencesService:
    return UserPreferencesService(repo)
