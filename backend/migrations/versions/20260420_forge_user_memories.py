"""add forge_user_memories table and memory fields on user_preferences

Revision ID: 20260420_forge_memory
Revises: 20260419_user_prefs
Create Date: 2026-04-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20260420_forge_memory"
down_revision: str = "20260419_user_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New table for per-user forge memory chunks
    op.create_table(
        "forge_user_memories",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "source_conv_ids",
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_forge_user_memories_user_id", "forge_user_memories", ["user_id"])

    # Add pgvector embedding column (1536 dims for text-embedding-3-small)
    # Table is empty at this point so no default needed — add nullable then constrain
    op.execute("ALTER TABLE forge_user_memories ADD COLUMN embedding vector(1536)")
    op.execute("ALTER TABLE forge_user_memories ALTER COLUMN embedding SET NOT NULL")

    # Add tsvector for BM25 full-text search (computed from content)
    op.execute(
        """
        ALTER TABLE forge_user_memories
        ADD COLUMN search_vector_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
    """
    )
    op.execute(
        "CREATE INDEX ix_forge_user_memories_fts ON forge_user_memories "
        "USING gin(search_vector_tsv)"
    )
    op.execute(
        "CREATE INDEX ix_forge_user_memories_vec ON forge_user_memories "
        "USING ivfflat(embedding vector_cosine_ops) WITH (lists = 10)"
    )

    # Add memory schedule columns to user_preferences
    op.add_column(
        "user_preferences",
        sa.Column(
            "memory_enabled",
            sa.Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "memory_compaction_day",
            sa.Integer,
            nullable=False,
            server_default=text("0"),
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "memory_compaction_hour",
            sa.Integer,
            nullable=False,
            server_default=text("3"),
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "memory_last_compacted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "memory_next_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Bootstrap next_run_at for existing rows: schedule 7 days from now
    op.execute(
        "UPDATE user_preferences SET memory_next_run_at = "
        "NOW() + INTERVAL '7 days' WHERE memory_enabled = true"
    )

    # Track which forge_executions have been compacted
    op.add_column(
        "forge_executions",
        sa.Column(
            "memory_compacted",
            sa.Boolean,
            nullable=False,
            server_default=text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("forge_executions", "memory_compacted")
    op.drop_column("user_preferences", "memory_next_run_at")
    op.drop_column("user_preferences", "memory_last_compacted_at")
    op.drop_column("user_preferences", "memory_compaction_hour")
    op.drop_column("user_preferences", "memory_compaction_day")
    op.drop_column("user_preferences", "memory_enabled")
    op.drop_table("forge_user_memories")
