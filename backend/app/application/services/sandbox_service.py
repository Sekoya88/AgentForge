import asyncio
import uuid

import redis.asyncio as redis

from app.domain.exceptions import StreamingNotAvailableError
from app.domain.ports.sandbox_runtime import SandboxRuntime
from app.infrastructure.events.redis_execution_stream import RedisStreamEmitter, sandbox_stream_key


class SandboxService:
    def __init__(self, runtime: SandboxRuntime, redis_client: redis.Redis | None) -> None:
        self._runtime = runtime
        self._redis = redis_client

    async def run_python(
        self,
        code: str,
        *,
        timeout_sec: float = 15.0,
        run_async: bool = False,
    ) -> tuple[str, int | None, str, str]:
        """
        Returns (job_id, exit_code, stdout, stderr).
        When run_async, schedules background task and returns exit_code None until finished.
        """
        job_id = str(uuid.uuid4())
        if run_async:
            if not self._redis:
                raise StreamingNotAvailableError()
            asyncio.create_task(self._run_bg(job_id, code, timeout_sec))
            return job_id, None, "", ""

        code_exit, out, err = await self._runtime.run_python(code, timeout_sec)
        return job_id, code_exit, out, err

    async def _run_bg(self, job_id: str, code: str, timeout_sec: float) -> None:
        assert self._redis is not None
        emitter = RedisStreamEmitter(self._redis, sandbox_stream_key(job_id))
        await emitter.emit("sandbox_start", {"job_id": job_id})
        try:
            code_exit, out, err = await self._runtime.run_python(code, timeout_sec)
            await emitter.emit(
                "sandbox_result",
                {"exit_code": code_exit, "stdout": out, "stderr": err},
            )
            await emitter.emit("complete", {"job_id": job_id})
        except Exception as e:
            await emitter.emit("error", {"message": str(e), "type": type(e).__name__})
