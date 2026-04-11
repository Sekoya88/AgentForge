import asyncio
import os as _os
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.middleware.correlation import CorrelationIdMiddleware
from app.api.middleware.error_handler import register_exception_handlers
from app.api.middleware.rate_limit import limiter
from app.api.middleware.request_logging import RequestLoggingMiddleware
from app.api.v1.router import api_router
from app.config import get_settings
from app.infrastructure.orchestration.checkpoint_registry import (
    setup_checkpoint_pool,
    teardown_checkpoint_pool,
)
from app.infrastructure.redis_client import connect_redis, disconnect_redis

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

_settings_for_sentry = get_settings()
if _settings_for_sentry.sentry_dsn:
    sentry_sdk.init(
        dsn=_settings_for_sentry.sentry_dsn,
        integrations=[FastApiIntegration(transaction_style="endpoint")],
        traces_sample_rate=_settings_for_sentry.sentry_traces_sample_rate,
        environment=_settings_for_sentry.sentry_environment,
        send_default_pii=False,
    )

# Set Langfuse/LangSmith env vars eagerly so @observe decorator can find them at init time
_obs_backend = _settings_for_sentry.observability_backend.lower()

if _obs_backend == "langfuse":
    if _settings_for_sentry.langfuse_public_key:
        _os.environ.setdefault("LANGFUSE_PUBLIC_KEY", _settings_for_sentry.langfuse_public_key)
    if _settings_for_sentry.langfuse_secret_key:
        _os.environ.setdefault("LANGFUSE_SECRET_KEY", _settings_for_sentry.langfuse_secret_key)
    if _settings_for_sentry.langfuse_host:
        _os.environ.setdefault("LANGFUSE_HOST", _settings_for_sentry.langfuse_host)
elif _obs_backend == "langsmith":
    _os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    _os.environ.setdefault("LANGFUSE_SDK_DISABLE", "true")
else:
    _os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
    _os.environ.setdefault("LANGFUSE_SDK_DISABLE", "true")


async def _resume_running_finetune_jobs() -> None:
    """Re-attach poll tasks for finetune jobs left in 'running' state after a restart."""
    import asyncio

    from app.config import get_settings as _gs
    from app.infrastructure.persistence.postgres.finetune_repo import PostgresFinetuneJobRepository
    from app.infrastructure.persistence.postgres.session import session_scope
    from app.infrastructure.redis_client import get_redis_client as get_redis

    settings = _gs()
    if not getattr(settings, "modal_enabled", False):
        return

    try:
        redis_client = get_redis()
    except Exception:
        redis_client = None

    async with session_scope() as session:
        repo = PostgresFinetuneJobRepository(session)
        from sqlalchemy import select

        from app.infrastructure.persistence.postgres.models import FinetuneJobModel

        result = await session.execute(
            select(FinetuneJobModel).where(FinetuneJobModel.status == "running")
        )
        running_jobs = result.scalars().all()

        if not running_jobs:
            return

        from app.application.services.finetune_service import FinetuneService

        svc = FinetuneService(repo, settings, redis_client)
        for job_row in running_jobs:
            if job_row.modal_job_id:
                structlog.get_logger().info(
                    "resuming_poll",
                    job_id=str(job_row.id),
                    modal_job_id=job_row.modal_job_id,
                )
                asyncio.create_task(
                    svc._poll_job(job_row.id, job_row.user_id, job_row.modal_job_id)
                )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.infrastructure.scheduling.tick import schedule_worker_loop

    settings = get_settings()
    obs = settings.observability_backend.lower()
    structlog.get_logger().info(
        "observability_effective",
        backend=obs,
        langfuse_keys_configured=bool(
            settings.langfuse_public_key and settings.langfuse_secret_key
        ),
        langsmith_key_configured=bool(settings.langsmith_api_key),
    )
    await connect_redis(settings.redis_url)
    await setup_checkpoint_pool()
    await _resume_running_finetune_jobs()
    schedule_stop = asyncio.Event()
    schedule_task = asyncio.create_task(schedule_worker_loop(schedule_stop))
    try:
        yield
    finally:
        schedule_stop.set()
        schedule_task.cancel()
        try:
            await schedule_task
        except asyncio.CancelledError:
            pass
        await teardown_checkpoint_pool()
        await disconnect_redis()


app = FastAPI(title="AgentForge API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_exception_handlers(app)
settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
origin_regex = (settings.cors_origin_regex or "").strip() or None
# Order (last add = outermost): CORS → access log → correlation → SlowAPI → routes.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=settings.cors_allow_private_network,
)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict:
    from sqlalchemy import text as sa_text

    from app.infrastructure.persistence.postgres.session import get_session_factory
    from app.infrastructure.redis_client import get_redis_client

    checks: dict[str, str] = {}

    # DB check
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(sa_text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # Redis check
    redis_client = get_redis_client()
    if redis_client is None:
        checks["redis"] = "unavailable"
    else:
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"

    overall = "ok" if all(v == "ok" for v in checks.values() if v != "unavailable") else "degraded"

    from fastapi.responses import JSONResponse

    status_code = 200 if overall == "ok" else 503
    return JSONResponse(content={"status": overall, "checks": checks}, status_code=status_code)
