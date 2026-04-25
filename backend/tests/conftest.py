import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

# Test env before any `app` import — main.py reads SENTRY_DSN at import time.
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-key-for-pytest-only-32chars!!",
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://forge:forge@localhost:5433/agentforge",
)
os.environ.setdefault(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
os.environ.setdefault("CORS_ALLOW_PRIVATE_NETWORK", "true")
os.environ["SENTRY_DSN"] = ""  # Force off: setdefault does not override a real DSN from .env/shell
os.environ["MODAL_ENABLED"] = "false"  # Avoid real Modal calls when dev .env enables it
os.environ["REDTEAM_MODE"] = "mock"  # Deterministic campaign counts vs local promptfoo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.middleware.rate_limit import limiter

_backend_root = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate limit counters between tests."""
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest_asyncio.fixture(autouse=True)
async def dispose_global_postgres_engine_after_test() -> AsyncIterator[None]:
    """/health uses get_session_factory() module singleton; loops differ per test."""
    yield
    from app.infrastructure.persistence.postgres import session as pg_session

    if pg_session._engine is not None:
        try:
            await pg_session._engine.dispose()
        except Exception:
            pass
        pg_session._engine = None
        pg_session._session_factory = None


@pytest.fixture(autouse=True)
def disable_audit_background_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Background audit tasks reuse the pool and race with test transactions."""
    from app.infrastructure import audit

    monkeypatch.setattr(audit, "log_audit_event", lambda *a, **kw: None)


@pytest.fixture(scope="session")
def alembic_ready() -> None:
    env = {**os.environ, "DATABASE_URL": os.environ["DATABASE_URL"]}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_backend_root,
        env=env,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        pytest.skip(f"Postgres/migrations unavailable: {r.stderr or r.stdout}")


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.commit()
    try:
        import asyncio

        await asyncio.wait_for(engine.dispose(), timeout=1.0)
    except Exception:
        pass


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.dependencies import get_session
    from app.main import app, lifespan

    url = os.environ["DATABASE_URL"]
    test_engine = create_async_engine(url, echo=False, poolclass=NullPool)
    test_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with test_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)

    async with lifespan(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()

    # Dispose the engine after tests
    import asyncio

    try:
        await asyncio.wait_for(test_engine.dispose(), timeout=1.0)
    except Exception:
        pass
