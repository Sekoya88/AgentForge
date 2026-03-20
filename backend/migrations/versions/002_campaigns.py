"""campaigns table for red-team

Revision ID: 002
Revises: 001
Create Date: 2025-03-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("overall_score", sa.Float()),
        sa.Column("total_tests", sa.Integer()),
        sa.Column("passed_tests", sa.Integer()),
        sa.Column("failed_tests", sa.Integer()),
        sa.Column("report", JSONB),
        sa.Column("vulnerabilities", JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("campaigns")
