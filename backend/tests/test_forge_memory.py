import uuid
from datetime import UTC, datetime

import pytest

from app.domain.entities.forge_memory import ForgeMemoryChunk
from app.domain.ports.forge_memory_repository import ForgeMemoryRepository


def test_forge_memory_chunk_defaults():
    chunk = ForgeMemoryChunk(
        user_id=uuid.uuid4(),
        content="User is a Python developer",
        embedding=[0.1] * 1536,
        period_start=datetime.now(UTC),
        period_end=datetime.now(UTC),
    )
    assert chunk.source_conv_ids == []
    assert chunk.id is None
    assert chunk.created_at is None


def test_forge_memory_repository_is_abstract():
    with pytest.raises(TypeError):
        ForgeMemoryRepository()


def test_forge_user_memory_model_importable():
    from app.infrastructure.persistence.postgres.models import ForgeUserMemoryModel

    assert ForgeUserMemoryModel.__tablename__ == "forge_user_memories"


def test_forge_memory_repo_implements_port():
    from app.infrastructure.persistence.postgres.forge_memory_repo import (
        PostgresForgeMemoryRepository,
    )

    assert issubclass(PostgresForgeMemoryRepository, ForgeMemoryRepository)


def test_forge_memory_service_importable():
    from app.application.services.forge_memory_service import ForgeMemoryService

    assert hasattr(ForgeMemoryService, "compact")
    assert hasattr(ForgeMemoryService, "retrieve_context")


def test_build_memory_context_format():
    import uuid
    from datetime import UTC, datetime

    from app.application.services.forge_memory_service import _format_memory_context
    from app.domain.entities.forge_memory import ForgeMemoryChunk

    chunks = [
        ForgeMemoryChunk(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            content="User builds AI agents in Python",
            embedding=[],
            period_start=datetime(2026, 3, 1, tzinfo=UTC),
            period_end=datetime(2026, 3, 31, tzinfo=UTC),
        )
    ]
    result = _format_memory_context(chunks)
    assert "User builds AI agents in Python" in result
    assert "2026-03" in result


def test_format_memory_context_empty():
    from app.application.services.forge_memory_service import _format_memory_context

    result = _format_memory_context([])
    assert result == ""
