"""initial schema users agents executions

Revision ID: 001
Revises:
Create Date: 2025-03-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("graph_definition", JSONB, nullable=False),
        sa.Column("model_config", JSONB, nullable=False),
        sa.Column("interrupt_config", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("skills", ARRAY(sa.Text()), server_default=sa.text("ARRAY[]::text[]")),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("security_score", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("input_messages", JSONB, nullable=False),
        sa.Column("output_messages", JSONB),
        sa.Column("interrupt_state", JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("token_usage", JSONB),
        sa.Column("duration_ms", sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table("executions")
    op.drop_table("agents")
    op.drop_table("users")
