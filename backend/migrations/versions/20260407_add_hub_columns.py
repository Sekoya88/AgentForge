"""add is_public and stars hub columns to agents

Revision ID: 20260407_add_hub_columns
Revises: 20260407_add_inbound_webhook_secret
Create Date: 2026-04-07
"""

import sqlalchemy as sa
from alembic import op

revision = "20260407_add_hub_columns"
down_revision = "20260407_add_inbound_webhook_secret"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "is_public",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "stars",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "stars")
    op.drop_column("agents", "is_public")
