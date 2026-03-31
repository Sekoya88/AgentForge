"""agent_schedules + execution trigger_source

Revision ID: 013_agent_schedules
Revises: 012_output_audio_b64
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013_agent_schedules"
down_revision = "012_output_audio_b64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("alias", sa.String(100), nullable=True),
        sa.Column("cron_expression", sa.String(128), nullable=False),
        sa.Column("input", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_agent_schedules_due",
        "agent_schedules",
        ["enabled", "next_run_at"],
    )
    op.add_column(
        "executions",
        sa.Column("trigger_source", sa.String(32), nullable=False, server_default="api"),
    )
    op.add_column(
        "executions",
        sa.Column(
            "schedule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_schedules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("executions", "schedule_id")
    op.drop_column("executions", "trigger_source")
    op.drop_index("ix_agent_schedules_due", table_name="agent_schedules")
    op.drop_table("agent_schedules")
