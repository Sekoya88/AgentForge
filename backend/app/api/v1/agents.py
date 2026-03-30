import base64
import json
from datetime import datetime
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

from app.api.middleware.rate_limit import limiter
from app.api.schemas.agent_schemas import (
    AgentAliasRequest,
    AgentCreateRequest,
    AgentImportRequest,
    AgentImportYamlRequest,
    AgentResponse,
    AgentUpdateRequest,
    ExecuteAgentRequest,
    ExecutionFeedbackRequest,
    ExecutionResponse,
    InterruptExecutionRequest,
)
from app.api.sse import redis_stream_sse
from app.application.services.agent_service import AgentService
from app.application.services.finetune_service import FinetuneService
from app.dependencies import (
    get_agent_service,
    get_current_user,
    get_finetune_service,
    get_redis_required,
)
from app.domain.entities.user import User
from app.domain.exceptions import AgentNotFoundError
from app.infrastructure.events.redis_execution_stream import execution_stream_key
from app.infrastructure.persistence.postgres.agent_repo import AgentVersion, PostgresAgentRepository

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_to_response(a) -> AgentResponse:
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
    )
    return _agent_to_response(a)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> None:
    await svc.delete(agent_id, user.id)


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
    )
    payload = jsonable_encoder(_exec_to_response(e))
    code = status.HTTP_202_ACCEPTED if body.run_async else status.HTTP_200_OK
    return JSONResponse(status_code=code, content=payload)


@router.post("/{agent_id}/execute/audio")
@limiter.limit("30/minute")
async def execute_agent_audio(
    request: Request,
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
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
    audio_b64 = base64.b64encode(audio_bytes).decode()
    e = await svc.execute(
        agent_id,
        user.id,
        msgs_raw,
        graph_extra={"audio_b64": audio_b64},
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
) -> ExecutionResponse:
    e = await svc.get_execution(agent_id, execution_id, user.id)
    return _exec_to_response(e)


@router.post(
    "/{agent_id}/executions/{execution_id}/feedback", status_code=status.HTTP_204_NO_CONTENT
)
async def post_execution_feedback(
    agent_id: UUID,
    execution_id: UUID,
    body: ExecutionFeedbackRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
    finetune_svc: Annotated[FinetuneService, Depends(get_finetune_service)],
) -> None:
    try:
        await svc.submit_execution_feedback(
            agent_id,
            execution_id,
            user.id,
            score=body.score,
            comment=body.comment,
        )
        if body.score >= 0.8:
            ex = await svc.get_execution(agent_id, execution_id, user.id)
            if ex.output_messages:
                await finetune_svc.save_example(
                    agent_id=agent_id,
                    user_id=user.id,
                    execution_id=execution_id,
                    input_messages=ex.input_messages,
                    output_messages=ex.output_messages,
                    score=body.score,
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
) -> dict:
    try:
        return await svc.export_agent(
            agent_id, user.id, include_skills=include_skills, version=version, alias=alias
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
