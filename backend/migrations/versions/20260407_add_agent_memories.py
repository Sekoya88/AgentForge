"""add_agent_memories

Revision ID: 20260407_add_agent_memories
Revises: 20260406_knowledge_chunk_metadata
Create Date: 2026-04-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260407_add_agent_memories"
down_revision = "20260406_chunk_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "agent_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text, nullable=False),  # stored as vector(1536) via raw SQL below
        sa.Column("importance", sa.Float, nullable=False, server_default="0.5"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Replace the Text column with a proper vector(1536) column
    op.execute(
        "ALTER TABLE agent_memories ALTER COLUMN embedding TYPE vector(1536) "
        "USING embedding::vector(1536)"
    )

    op.create_index("ix_agent_memories_user_id", "agent_memories", ["user_id"])
    op.create_index("ix_agent_memories_agent_id", "agent_memories", ["agent_id"])

    # IVFFLAT index for approximate nearest-neighbor cosine search
    op.execute(
        "CREATE INDEX ix_agent_memories_embedding ON agent_memories "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_table("agent_memories")
