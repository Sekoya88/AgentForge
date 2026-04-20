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
