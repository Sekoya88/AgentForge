import base64
import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import redis.asyncio as redis
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.rate_limit import limiter
from app.api.schemas.agent_schemas import (
    AgentAliasRequest,
    AgentCompareRequest,
    AgentCompareResponse,
    AgentCreateRequest,
    AgentImportBundle,
    AgentImportRequest,
    AgentImportYamlRequest,
    AgentResponse,
    AgentScheduleCreateRequest,
    AgentScheduleResponse,
    AgentScheduleUpdateRequest,
    AgentUpdateRequest,
    ChatMessage,
    ConversationCreateRequest,
    ConversationResponse,
    ExecuteAgentRequest,
    ExecutionFeedbackRequest,
    ExecutionResponse,
    InterruptExecutionRequest,
)
from app.api.sse import redis_stream_sse
from app.application.services.agent_service import AgentService
from app.dependencies import (
    get_agent_service,
    get_current_user,
    get_redis_required,
    get_s3_audio_store,
    get_session,
)
from app.domain.entities.user import User
from app.domain.exceptions import AgentNotFoundError, StreamingNotAvailableError
from app.domain.services.pii_masker import PiiMasker
from app.infrastructure.events.redis_execution_stream import execution_stream_key
from app.infrastructure.persistence.postgres.agent_repo import AgentVersion, PostgresAgentRepository
from app.infrastructure.persistence.postgres.models import ConversationModel
from app.infrastructure.storage.s3_store import S3AudioStore

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_to_response(a) -> AgentResponse:
    secret = getattr(a, "inbound_webhook_secret", None)
    webhook_url = f"/api/v1/agents/{a.id}/webhook/{secret}" if secret else None
    return AgentResponse(
        id=a.id,
        user_id=a.user_id,
        name=a.name,
        description=a.description,
        graph_definition=a.graph_definition.to_dict(),
        llm_model_config=a.model_config.to_dict(),
        interrupt_config=a.interrupt_config.to_dict(),
        skills=a.skills,
        status=a.status,
        security_score=a.security_score,
        health_score=a.health_score,
        collect_speech_examples=a.collect_speech_examples,
        inbound_webhook_secret=secret,
        inbound_webhook_url=webhook_url,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _exec_to_response(e) -> ExecutionResponse:
    return ExecutionResponse(
        id=e.id,
        agent_id=e.agent_id,
        user_id=e.user_id,
        thread_id=e.thread_id,
        status=e.status,
        input_messages=e.input_messages,
        output_messages=e.output_messages,
        interrupt_state=e.interrupt_state,
        started_at=e.started_at,
        completed_at=e.completed_at,
        token_usage=e.token_usage,
        duration_ms=e.duration_ms,
        agent_version_number=e.agent_version_number,
        output_audio_b64=e.output_audio_b64,
        output_audio_url=e.output_audio_url,
        trigger_source=e.trigger_source,
        schedule_id=e.schedule_id,
        compare_group_id=e.compare_group_id,
        compare_label=e.compare_label,
        model_config_override=e.model_config_override,
    )


def _schedule_to_response(s) -> AgentScheduleResponse:
    return AgentScheduleResponse(
        id=s.id,
        agent_id=s.agent_id,
        user_id=s.user_id,
        alias=s.alias,
        cron_expression=s.cron_expression,
        input=s.input,
        enabled=s.enabled,
        last_run_at=s.last_run_at,
        next_run_at=s.next_run_at,
        created_at=s.created_at,
    )


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    a = await svc.create(
        user.id,
        body.name,
        body.description,
        body.graph_definition,
        body.llm_model_config,
        skills=body.skills,
        execution_policy=body.execution_policy,
        collect_speech_examples=body.collect_speech_examples,
    )
    return _agent_to_response(a)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> list[AgentResponse]:
    agents = await svc.list_agents(user.id)
    return [_agent_to_response(a) for a in agents]


@router.post("/import", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def import_agent(
    body: AgentImportRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    raw = body.model_dump(by_alias=True)
    a = await svc.import_agent(user.id, raw, name_override=body.name)
    return _agent_to_response(a)


@router.post("/import-yaml", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def import_agent_yaml(
    body: AgentImportYamlRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    try:
        a = await svc.import_yaml(user.id, body.yaml_content, name_override=body.name)
        return _agent_to_response(a)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{agent_id}/share")
async def create_share_link(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    permission: Annotated[str, Query()] = "view",
) -> dict:
    """Create a shareable link for the agent."""
    import secrets as _secrets

    from app.infrastructure.persistence.postgres.models import AgentModel as _AgentModel
    from app.infrastructure.persistence.postgres.models import ShareTokenModel

    agent = await session.get(_AgentModel, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    tok = _secrets.token_urlsafe(32)
    share = ShareTokenModel(token=tok, agent_id=agent_id, permission=permission)
    session.add(share)
    await session.commit()
    return {"token": tok, "share_url": f"/shared/{tok}", "permission": permission}


@router.get("/shared/{token}")
async def get_shared_agent(
    token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Public endpoint — returns agent definition for view permission."""
    from sqlalchemy import select as _select

    from app.infrastructure.persistence.postgres.models import AgentModel as _AgentModel
    from app.infrastructure.persistence.postgres.models import ShareTokenModel

    result = await session.execute(_select(ShareTokenModel).where(ShareTokenModel.token == token))
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Invalid or expired share link")
    if share.expires_at and share.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Share link has expired")

    agent = await session.get(_AgentModel, share.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "id": str(agent.id),
        "name": agent.name,
        "description": agent.description,
        "graph_definition": agent.graph_definition,
        "permission": share.permission,
        "node_count": len(agent.graph_definition.get("nodes", [])) if agent.graph_definition else 0,
    }


@router.post("/shared/{token}/execute", status_code=202)
async def execute_shared_agent(
    token: str,
    body: dict,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Execute a shared agent (requires execute permission)."""
    from sqlalchemy import select as _select

    from app.infrastructure.persistence.postgres.models import ShareTokenModel

    result = await session.execute(_select(ShareTokenModel).where(ShareTokenModel.token == token))
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Invalid share link")
    if share.permission != "execute":
        raise HTTPException(status_code=403, detail="This link only allows viewing")
    if share.expires_at and share.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Share link has expired")

    return {
        "accepted": True,
        "agent_id": str(share.agent_id),
        "note": "Execute via POST /agents/{id}/execute with auth",
    }


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    a = await svc.get(agent_id, user.id)
    return _agent_to_response(a)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    body: AgentUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    a = await svc.update(
        agent_id,
        user.id,
        body.name,
        body.description,
        body.graph_definition,
        body.llm_model_config,
        body.status,
        interrupt_config=body.interrupt_config,
        skills=body.skills,
        execution_policy=body.execution_policy,
        collect_speech_examples=body.collect_speech_examples,
    )
    return _agent_to_response(a)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> None:
    await svc.delete(agent_id, user.id)


@router.post(
    "/{agent_id}/schedules",
    response_model=AgentScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_schedule(
    agent_id: UUID,
    body: AgentScheduleCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentScheduleResponse:
    s = await svc.create_schedule(
        agent_id,
        user.id,
        body.cron_expression,
        body.input,
        alias=body.alias,
        enabled=body.enabled,
    )
    return _schedule_to_response(s)


@router.get("/{agent_id}/schedules", response_model=list[AgentScheduleResponse])
async def list_agent_schedules(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> list[AgentScheduleResponse]:
    rows = await svc.list_schedules(agent_id, user.id)
    return [_schedule_to_response(s) for s in rows]


@router.get("/{agent_id}/schedules/{schedule_id}", response_model=AgentScheduleResponse)
async def get_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentScheduleResponse:
    s = await svc.get_schedule(agent_id, user.id, schedule_id)
    return _schedule_to_response(s)


@router.patch("/{agent_id}/schedules/{schedule_id}", response_model=AgentScheduleResponse)
async def patch_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    body: AgentScheduleUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentScheduleResponse:
    patch = body.model_dump(exclude_unset=True)
    set_alias = "alias" in patch
    alias_val = patch.get("alias") if set_alias else None
    s = await svc.update_schedule(
        agent_id,
        user.id,
        schedule_id,
        cron_expression=patch.get("cron_expression"),
        input_payload=patch.get("input"),
        set_alias=set_alias,
        alias=alias_val,
        enabled=patch.get("enabled"),
    )
    return _schedule_to_response(s)


@router.delete("/{agent_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> None:
    await svc.delete_schedule(agent_id, user.id, schedule_id)


@router.post("/{agent_id}/execute")
@limiter.limit("30/minute")
async def execute_agent(
    request: Request,
    agent_id: UUID,
    body: ExecuteAgentRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> JSONResponse:
    e = await svc.execute(
        agent_id,
        user.id,
        body.input_messages,
        run_async=body.run_async,
        version=body.version,
        alias=body.alias,
        thread_id=body.thread_id,
    )
    payload = jsonable_encoder(_exec_to_response(e))
    code = status.HTTP_202_ACCEPTED if body.run_async else status.HTTP_200_OK
    return JSONResponse(status_code=code, content=payload)


@router.post("/{agent_id}/compare", response_model=AgentCompareResponse)
@limiter.limit("30/minute")
async def compare_agent_executions(
    request: Request,
    agent_id: UUID,
    body: AgentCompareRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentCompareResponse:
    variants = [(v.label, v.model_config_override) for v in body.variants]
    try:
        group_id, executions = await svc.compare_executions(
            agent_id,
            user.id,
            body.message,
            variants,
            run_async=body.run_async,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    except StreamingNotAvailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async execution requires Redis",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return AgentCompareResponse(
        compare_group_id=group_id,
        executions=[_exec_to_response(e) for e in executions],
    )


@router.post("/{agent_id}/execute/audio")
@limiter.limit("30/minute")
async def execute_agent_audio(
    request: Request,
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
    s3: Annotated[S3AudioStore, Depends(get_s3_audio_store)],
    file: UploadFile = File(...),
    input_messages: str = Form(default='[{"role":"user","content":""}]'),
) -> JSONResponse:
    """Run agent with binary audio: body is multipart (file + optional input_messages JSON)."""
    try:
        msgs_raw = json.loads(input_messages)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input_messages JSON: {e}",
        ) from e
    if not isinstance(msgs_raw, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="input_messages must be a JSON array",
        )
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file",
        )
    # The orchestrator always needs base64 in-memory for ASR/TTS nodes.
    audio_b64 = base64.b64encode(audio_bytes).decode()
    graph_extra: dict[str, Any] = {"audio_b64": audio_b64}
    # When S3 is enabled, also persist a copy to object storage so the
    # execution record stores a URL instead of the full blob.
    if s3.enabled:
        ext = (file.filename or "bin").rsplit(".", 1)[-1] or "bin"
        key = await s3.upload(audio_bytes, prefix="execution-audio/input", ext=ext)
        graph_extra["input_audio_url"] = key
    e = await svc.execute(
        agent_id,
        user.id,
        msgs_raw,
        graph_extra=graph_extra,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(_exec_to_response(e)),
    )


@router.get("/{agent_id}/stream/{execution_id}")
async def stream_agent_execution(
    agent_id: UUID,
    execution_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
    r: Annotated[redis.Redis, Depends(get_redis_required)],
) -> StreamingResponse:
    await svc.get_execution(agent_id, execution_id, user.id)
    key = execution_stream_key(execution_id)
    return StreamingResponse(
        redis_stream_sse(r, key),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{agent_id}/executions", response_model=list[ExecutionResponse])
async def list_executions(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> list[ExecutionResponse]:
    xs = await svc.list_executions(agent_id, user.id)
    return [_exec_to_response(x) for x in xs]


@router.get("/{agent_id}/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    agent_id: UUID,
    execution_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
    mask_pii: Annotated[
        bool, Query(description="Redact PII from output_messages before returning")
    ] = False,
) -> ExecutionResponse:
    e = await svc.get_execution(agent_id, execution_id, user.id)
    response = _exec_to_response(e)
    if mask_pii and response.output_messages:
        response.output_messages = PiiMasker().mask_messages(response.output_messages)
    return response


@router.post(
    "/{agent_id}/executions/{execution_id}/feedback", status_code=status.HTTP_204_NO_CONTENT
)
async def post_execution_feedback(
    agent_id: UUID,
    execution_id: UUID,
    body: ExecutionFeedbackRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> None:
    try:
        await svc.submit_execution_feedback(
            agent_id,
            execution_id,
            user.id,
            score=body.score,
            comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/{agent_id}/executions/{execution_id}/interrupt", response_model=ExecutionResponse)
async def interrupt_execution(
    agent_id: UUID,
    execution_id: UUID,
    body: InterruptExecutionRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> ExecutionResponse:
    e = await svc.resume_execution(agent_id, execution_id, user.id, body.decisions)
    return _exec_to_response(e)


class AgentVersionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    version_number: int
    graph_definition: Any
    llm_model_config: Any
    skills: list[str]
    execution_policy: dict[str, Any]
    change_note: str | None
    created_at: datetime


def _version_to_response(v: AgentVersion) -> AgentVersionResponse:
    return AgentVersionResponse(
        id=v.id,
        agent_id=v.agent_id,
        version_number=v.version_number,
        graph_definition=v.graph_definition,
        llm_model_config=v.model_config,
        skills=v.skills,
        execution_policy=v.execution_policy,
        change_note=v.change_note,
        created_at=v.created_at,
    )


def _get_version_repo(svc: AgentService) -> PostgresAgentRepository:
    repo = svc._repo
    if not isinstance(repo, PostgresAgentRepository):
        raise HTTPException(status_code=500, detail="Version history unavailable")
    return repo


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
async def list_agent_versions(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> list[AgentVersionResponse]:
    repo = _get_version_repo(svc)
    versions = await repo.list_versions(agent_id, user.id)
    return [_version_to_response(v) for v in versions]


@router.post("/{agent_id}/aliases", status_code=status.HTTP_204_NO_CONTENT)
async def set_agent_alias(
    agent_id: UUID,
    body: AgentAliasRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> None:
    repo = _get_version_repo(svc)
    try:
        await repo.set_alias(agent_id, user.id, body.name, body.version_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{agent_id}/aliases")
async def list_agent_aliases(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> dict[str, int]:
    repo = _get_version_repo(svc)
    return await repo.list_aliases(agent_id, user.id)


@router.get("/{agent_id}/versions/{version_number}", response_model=AgentVersionResponse)
async def get_agent_version(
    agent_id: UUID,
    version_number: int,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentVersionResponse:
    repo = _get_version_repo(svc)
    v = await repo.get_version(agent_id, user.id, version_number)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return _version_to_response(v)


@router.get("/{agent_id}/versions/diff")
async def diff_agent_versions_api(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
    from_version: Annotated[int, Query(alias="from", ge=1, description="Source version number")],
    to_version: Annotated[int, Query(alias="to", ge=1, description="Target version number")],
) -> dict[str, Any]:
    try:
        return await svc.diff_agent_versions(agent_id, user.id, from_version, to_version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.get("/{agent_id}/scorecard")
async def agent_scorecard(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> dict[str, Any]:
    try:
        return await svc.get_agent_scorecard(agent_id, user.id)
    except TypeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from None


@router.get("/{agent_id}/stats/versions")
async def agent_stats_by_version(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> list[dict[str, Any]]:
    """Execution statistics aggregated per agent version."""
    try:
        return await svc.get_version_stats(agent_id, user.id)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")
    except TypeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from None


@router.post("/{agent_id}/rollback/{version_number}", response_model=AgentResponse)
async def rollback_agent(
    agent_id: UUID,
    version_number: int,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    repo = _get_version_repo(svc)
    a = await repo.rollback_to_version(agent_id, user.id, version_number)
    if not a:
        raise HTTPException(status_code=404, detail="Agent or version not found")
    return _agent_to_response(a)


@router.delete("/{agent_id}/versions/{version_number}", status_code=204)
async def delete_agent_version(
    agent_id: UUID,
    version_number: int,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> None:
    repo = _get_version_repo(svc)
    deleted = await repo.delete_version(agent_id, user.id, version_number)
    if not deleted:
        raise HTTPException(
            status_code=400,
            detail="Version not found or cannot delete the current version",
        )


@router.post("/{agent_id}/conversations", status_code=201, response_model=ConversationResponse)
async def create_conversation(
    agent_id: UUID,
    body: ConversationCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationResponse:
    from uuid import uuid4

    now = datetime.utcnow()
    conv = ConversationModel(
        id=uuid4(),
        user_id=current_user.id,
        agent_id=agent_id,
        thread_id=str(uuid4()),
        title=body.title,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.get("/{agent_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[ConversationResponse]:
    result = await db.execute(
        select(ConversationModel)
        .where(ConversationModel.user_id == current_user.id, ConversationModel.agent_id == agent_id)
        .order_by(ConversationModel.updated_at.desc())
    )
    rows = result.scalars().all()
    return [ConversationResponse.model_validate(r) for r in rows]


@router.get("/{agent_id}/conversations/{conv_id}/messages")
async def get_conversation_messages(
    agent_id: UUID,
    conv_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[ChatMessage]:
    result = await db.execute(
        select(ConversationModel).where(
            ConversationModel.id == conv_id,
            ConversationModel.user_id == current_user.id,
            ConversationModel.agent_id == agent_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    from app.infrastructure.persistence.postgres.models import ExecutionModel

    exec_result = await db.execute(
        select(ExecutionModel)
        .where(ExecutionModel.thread_id == conv.thread_id)
        .order_by(ExecutionModel.started_at.asc())
    )
    executions = exec_result.scalars().all()

    messages: list[ChatMessage] = []
    for exe in executions:
        for msg in exe.input_messages or []:
            if msg.get("role") == "user":
                messages.append(ChatMessage(role="user", content=msg.get("content") or ""))
        for msg in exe.output_messages or []:
            if msg.get("role") == "assistant":
                messages.append(ChatMessage(role="assistant", content=msg.get("content") or ""))
    return messages


@router.delete("/{agent_id}/conversations/{conv_id}", status_code=204)
async def delete_conversation(
    agent_id: UUID,
    conv_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    result = await db.execute(
        select(ConversationModel).where(
            ConversationModel.id == conv_id, ConversationModel.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    await db.delete(conv)


@router.get("/{agent_id}/export")
async def export_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
    include_skills: bool = Query(
        default=False, description="Embed full skill source code in export"
    ),
    version: int | None = Query(default=None, description="Export a specific version number"),
    alias: str | None = Query(
        default=None, description="Export a specific alias (e.g. 'production')"
    ),
) -> JSONResponse:
    try:
        agent_data = await svc.export_agent(
            agent_id, user.id, include_skills=include_skills, version=version, alias=alias
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    agent = await svc.get(agent_id, user.id)
    graph_def = agent_data.get("graph_definition", {})
    nodes = graph_def.get("nodes", []) if isinstance(graph_def, dict) else []
    model_cfg = agent_data.get("model_config", {}) or {}
    bundle = {
        "agentforge_version": "2.0",
        "exported_at": datetime.now(UTC).isoformat(),
        "metadata": {
            "name": agent_data.get("name", ""),
            "description": agent_data.get("description") or "",
            "use_case": f"Agent: {agent_data.get('name', '')}",
            "required_providers": list(
                {
                    node.get("config", {}).get("provider", model_cfg.get("provider", "unknown"))
                    for node in nodes
                    if node.get("type") in ("llm", "asr", "tts")
                }
            ),
            "required_skills": [
                node.get("config", {}).get("tool_name", "")
                for node in nodes
                if node.get("type") == "tool" and node.get("config", {}).get("tool_name")
            ],
            "node_count": len(nodes),
            "has_voice": any(n.get("type") in ("asr", "tts") for n in nodes),
        },
        "agent": {
            "name": agent_data.get("name"),
            "description": agent_data.get("description"),
            "graph_definition": graph_def,
            "model_config": model_cfg,
            "execution_policy": agent_data.get("execution_policy") or {},
            "interrupt_config": agent_data.get("interrupt_config") or {},
        },
        "skills": agent_data.get("skills", []),
        "sdk_usage": {
            "python": (
                "from agentforge_sdk import AgentForgeClient\nimport json\n\n"
                'client = AgentForgeClient(base_url="YOUR_URL", api_key="YOUR_KEY")\n\n'
                "# Import this agent\n"
                'with open("agent.json") as f:\n'
                "    bundle = json.load(f)\n"
                "agent = client.agents.import_bundle(bundle)\n\n"
                "# Run it\n"
                'result = client.agents.run(agent_id=agent.id, message="Hello!")\n'
                "print(result.output)"
            ),
            "curl": (
                "curl -X POST YOUR_URL/api/v1/agents/import-bundle"
                ' -H "Authorization: Bearer YOUR_KEY"'
                ' -H "Content-Type: application/json"'
                " -d @agent.json"
            ),
        },
    }
    filename = f"agent-{agent.name.replace(' ', '-')}.json"
    return JSONResponse(
        content=bundle,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


class SuggestConnectionsRequest(BaseModel):
    nodes: list[dict]  # [{id: str, type: str}]
    new_node_id: str


class ConnectionSuggestion(BaseModel):
    source: str
    target: str
    label: str | None = None


class SuggestConnectionsResponse(BaseModel):
    suggestions: list[ConnectionSuggestion]


# Heuristic rules: (source_type, target_type) → label
_CONNECTION_RULES: list[tuple[str, str, str | None]] = [
    ("asr", "llm", "audio→text"),
    ("llm", "tts", "text→audio"),
    ("memory_recall", "llm", "context"),
    ("llm", "memory_save", "save"),
    ("llm", "tool", "call"),
    ("tool", "llm", "result"),
    ("llm", "conditional", "route"),
    ("llm", "interrupt", "review"),
]


def _suggest_connections(nodes: list[dict], new_node_id: str) -> list[ConnectionSuggestion]:
    """Return up to 3 heuristic connection suggestions for the newly added node."""
    new_node = next((n for n in nodes if n["id"] == new_node_id), None)
    if not new_node:
        return []

    new_type = new_node.get("type", "")
    existing = [n for n in nodes if n["id"] != new_node_id]
    suggestions: list[ConnectionSuggestion] = []

    for existing_node in existing:
        existing_type = existing_node.get("type", "")
        # Check if existing_node → new_node matches a rule
        for src_t, tgt_t, label in _CONNECTION_RULES:
            if existing_type == src_t and new_type == tgt_t:
                suggestions.append(
                    ConnectionSuggestion(
                        source=existing_node["id"],
                        target=new_node_id,
                        label=label,
                    )
                )
                break
        # Check if new_node → existing_node matches a rule
        for src_t, tgt_t, label in _CONNECTION_RULES:
            if new_type == src_t and existing_type == tgt_t:
                suggestions.append(
                    ConnectionSuggestion(
                        source=new_node_id,
                        target=existing_node["id"],
                        label=label,
                    )
                )
                break
        if len(suggestions) >= 3:
            break

    return suggestions[:3]


@router.post("/{agent_id}/suggest-connections", response_model=SuggestConnectionsResponse)
async def suggest_connections(
    agent_id: UUID,
    body: SuggestConnectionsRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> SuggestConnectionsResponse:
    """Return heuristic-based connection suggestions for a newly added node."""
    # Verify the agent belongs to the user
    await svc.get(agent_id, user.id)
    suggestions = _suggest_connections(body.nodes, body.new_node_id)
    return SuggestConnectionsResponse(suggestions=suggestions)


@router.post("/import-bundle", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def import_agent_bundle(
    body: AgentImportBundle,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """Import an agent from a portable JSON bundle (agentforge_version format)."""
    if not body.agentforge_version:
        raise HTTPException(status_code=400, detail="Invalid bundle: missing agentforge_version")
    agent_data = body.agent
    if not agent_data.get("name"):
        raise HTTPException(status_code=400, detail="Invalid bundle: missing agent.name")
    graph_def = agent_data.get("graph_definition")
    if not isinstance(graph_def, dict) or not isinstance(graph_def.get("nodes"), list):
        raise HTTPException(
            status_code=400,
            detail="Invalid bundle: missing agent.graph_definition with nodes list",
        )
    # Merge skills from the bundle top-level into the agent payload for import
    payload: dict = {
        "name": agent_data.get("name"),
        "description": agent_data.get("description"),
        "graph_definition": graph_def,
        "model_config": agent_data.get("model_config", {}),
        "execution_policy": agent_data.get("execution_policy"),
        "interrupt_config": agent_data.get("interrupt_config"),
        "skills": body.skills,
    }
    a = await svc.import_agent(user.id, payload)
    return _agent_to_response(a)


@router.post("/{agent_id}/webhook/{secret}", status_code=status.HTTP_202_ACCEPTED)
async def inbound_webhook(
    agent_id: UUID,
    secret: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> dict:
    """Receive an external payload and trigger agent execution.

    No authentication header required — the URL secret acts as the access token.
    """

    from app.infrastructure.persistence.postgres.models import AgentModel as _AgentModel

    agent_model = await session.get(_AgentModel, agent_id)
    if not agent_model:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent_model.inbound_webhook_secret or agent_model.inbound_webhook_secret != secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    input_text = (
        payload.get("message") or payload.get("text") or payload.get("body") or str(payload)
    )

    execution = await svc.execute(
        agent_id,
        agent_model.user_id,
        [{"role": "user", "content": input_text}],
        trigger_source="webhook",
    )

    return {"accepted": True, "execution_id": str(execution.id)}


@router.post("/{agent_id}/health-score/refresh")
async def refresh_health_score(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    from app.application.services.health_score_service import refresh_agent_health_score

    score = await refresh_agent_health_score(agent_id, user.id, session)
    return {"agent_id": str(agent_id), "health_score": score}
