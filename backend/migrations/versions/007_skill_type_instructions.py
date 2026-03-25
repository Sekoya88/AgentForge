"""add skill_type and instructions columns to skills

Revision ID: 007
Revises: 006
Create Date: 2026-03-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "skills", sa.Column("skill_type", sa.String(20), server_default="code", nullable=False)
    )
    op.add_column("skills", sa.Column("instructions", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("skills", "instructions")
    op.drop_column("skills", "skill_type")
