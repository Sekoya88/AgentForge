"""Add execution_rate_limit to users table.

Revision ID: 20260408_user_rate_limit
Revises: 20260408_agent_budget
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op

revision = "20260408_user_rate_limit"
down_revision = "20260408_agent_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "execution_rate_limit",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "execution_rate_limit")
