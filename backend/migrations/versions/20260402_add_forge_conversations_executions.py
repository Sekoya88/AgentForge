"""add forge conversations and executions tables"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20260402_forge_tables"
down_revision: str | Sequence[str] | None = "20260402_tavily_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forge_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("thread_id", sa.String(255), unique=True, nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="anthropic"),
        sa.Column("model", sa.String(100), nullable=False, server_default="claude-sonnet-4-6"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_forge_conversations_user_id", "forge_conversations", ["user_id"])

    op.create_table(
        "forge_executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("forge_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("input_messages", JSONB, nullable=False),
        sa.Column("output_messages", JSONB, nullable=True),
        sa.Column("token_usage", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
    )
    op.create_index("ix_forge_executions_thread_id", "forge_executions", ["thread_id"])
    op.create_index("ix_forge_executions_conversation_id", "forge_executions", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_forge_executions_conversation_id", table_name="forge_executions")
    op.drop_index("ix_forge_executions_thread_id", table_name="forge_executions")
    op.drop_table("forge_executions")
    op.drop_index("ix_forge_conversations_user_id", table_name="forge_conversations")
    op.drop_table("forge_conversations")
