import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-key-for-pytest-only-32chars!!",
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://forge:forge@localhost:5433/agentforge",
)
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

_backend_root = Path(__file__).resolve().parents[1]


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
    engine = create_async_engine(url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.commit()
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.dependencies import get_session
    from app.main import app

    async def _override_session() -> AsyncIterator[AsyncSession]:
        url = os.environ["DATABASE_URL"]
        engine = create_async_engine(url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        await engine.dispose()

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
