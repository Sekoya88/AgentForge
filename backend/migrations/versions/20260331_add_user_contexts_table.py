"""Add user_contexts table

Revision ID: 20260331_user_contexts
Revises: 20260331_conversations
Create Date: 2026-03-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "20260331_user_contexts"
down_revision: str | None = "20260331_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_contexts",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("preferences", JSONB(), nullable=False, server_default="{}"),
        sa.Column("custom_data", JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_contexts")
