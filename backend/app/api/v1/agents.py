from typing import Annotated
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.schemas.agent_schemas import (
    AgentCreateRequest,
    AgentImportRequest,
    AgentResponse,
    AgentUpdateRequest,
    ExecuteAgentRequest,
    ExecutionResponse,
    InterruptExecutionRequest,
)
from app.api.sse import redis_stream_sse
from app.application.services.agent_service import AgentService
from app.dependencies import get_agent_service, get_current_user, get_redis_required
from app.domain.entities.user import User
from app.infrastructure.events.redis_execution_stream import execution_stream_key

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
async def execute_agent(
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
    )
    payload = jsonable_encoder(_exec_to_response(e))
    code = status.HTTP_202_ACCEPTED if body.run_async else status.HTTP_200_OK
    return JSONResponse(status_code=code, content=payload)


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


@router.get("/{agent_id}/export")
async def export_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> dict:
    return await svc.export_agent(agent_id, user.id)
