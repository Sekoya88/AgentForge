"""add scopes array to social_accounts for Google OAuth

Revision ID: 20260331_social_scopes
Revises: 20260331_merge_v2_heads
Create Date: 2026-03-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "20260331_social_scopes"
down_revision: str | None = "20260331_merge_v2_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "social_accounts",
        sa.Column(
            "scopes",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("social_accounts", "scopes")
