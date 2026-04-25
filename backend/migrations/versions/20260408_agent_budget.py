"""add budget_limit_usd and budget_alert_threshold to agents

Revision ID: 20260408_agent_budget
Revises: 20260408_workspace_members
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op

revision = "20260408_agent_budget"
down_revision = "20260408_workspace_members"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("budget_limit_usd", sa.Float(), nullable=True))
    op.add_column(
        "agents",
        sa.Column(
            "budget_alert_threshold",
            sa.Float(),
            nullable=False,
            server_default="0.8",
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "budget_alert_threshold")
    op.drop_column("agents", "budget_limit_usd")
