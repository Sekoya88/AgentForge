from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.schemas.sandbox_schemas import SandboxRunRequest, SandboxRunResponse
from app.api.sse import redis_stream_sse
from app.application.services.sandbox_service import SandboxService
from app.dependencies import get_current_user, get_redis_required, get_sandbox_service
from app.domain.entities.user import User
from app.infrastructure.events.redis_execution_stream import sandbox_stream_key

router = APIRouter(tags=["sandbox"])


@router.post("/sandbox/run")
async def sandbox_run(
    body: SandboxRunRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[SandboxService, Depends(get_sandbox_service)],
) -> JSONResponse:
    _ = user
    job_id, exit_code, out, err = await svc.run_python(
        body.code,
        timeout_sec=body.timeout_sec,
        run_async=body.run_async,
    )
    res = SandboxRunResponse(job_id=job_id, exit_code=exit_code, stdout=out, stderr=err)
    code = status.HTTP_202_ACCEPTED if body.run_async else status.HTTP_200_OK
    return JSONResponse(status_code=code, content=res.model_dump(mode="json"))


@router.get("/sandbox/stream/{job_id}")
async def sandbox_stream(
    job_id: str,
    user: Annotated[User, Depends(get_current_user)],
    r: Annotated[redis.Redis, Depends(get_redis_required)],
) -> StreamingResponse:
    _ = user
    key = sandbox_stream_key(job_id)
    return StreamingResponse(
        redis_stream_sse(r, key),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
