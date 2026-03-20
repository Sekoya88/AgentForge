from pydantic import BaseModel, Field


class SandboxRunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50_000)
    language: str = Field(default="python", pattern="^(python)$")
    timeout_sec: float = Field(default=15.0, ge=1.0, le=120.0)
    run_async: bool = Field(
        default=False,
        description="Stream output via GET /sandbox/stream/{job_id} (requires Redis).",
    )


class SandboxRunResponse(BaseModel):
    job_id: str
    exit_code: int | None
    stdout: str
    stderr: str
