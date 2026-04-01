"""add compare_group_id, compare_label, model_config_override on executions

Revision ID: 20260401_exec_compare
Revises: 20260331_social_scopes
Create Date: 2026-04-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20260401_exec_compare"
down_revision: str | Sequence[str] | None = "20260331_social_scopes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("compare_group_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "executions",
        sa.Column("compare_label", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "executions",
        sa.Column("model_config_override", JSONB, nullable=True),
    )
    op.create_index(
        "ix_executions_compare_group_id",
        "executions",
        ["compare_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_executions_compare_group_id", table_name="executions")
    op.drop_column("executions", "model_config_override")
    op.drop_column("executions", "compare_label")
    op.drop_column("executions", "compare_group_id")
