"""add health_score column to agents

Revision ID: add_health_score
Revises: add_audit_log
Create Date: 2026-04-07
"""

import sqlalchemy as sa
from alembic import op

revision = "add_health_score"
down_revision = "add_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("health_score", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "health_score")
