from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.correlation import CorrelationIdMiddleware
from app.api.middleware.error_handler import register_exception_handlers
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    await connect_redis(settings.redis_url)
    await setup_checkpoint_pool()
    yield
    await teardown_checkpoint_pool()
    await disconnect_redis()


app = FastAPI(title="AgentForge API", version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)
settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
origin_regex = (settings.cors_origin_regex or "").strip() or None
# CORS must be the outermost middleware (added last) so preflight OPTIONS is handled first.
app.add_middleware(CorrelationIdMiddleware)
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
async def health() -> dict[str, str]:
    return {"status": "ok"}
