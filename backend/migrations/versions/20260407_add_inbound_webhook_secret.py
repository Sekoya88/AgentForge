"""add inbound_webhook_secret to agents

Revision ID: 20260407_inbound_wh_secret
Revises: 20260407_add_agent_memories
Create Date: 2026-04-07

Note: revision id must fit alembic_version.version_num (VARCHAR(32)).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260407_inbound_wh_secret"
down_revision = "20260407_add_agent_memories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("inbound_webhook_secret", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "inbound_webhook_secret")
