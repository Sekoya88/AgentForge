"""Add encrypted_anthropic_key to user_secrets

Revision ID: 010
Revises: 009
Create Date: 2026-03-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_secrets", sa.Column("encrypted_anthropic_key", sa.String(512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_secrets", "encrypted_anthropic_key")
