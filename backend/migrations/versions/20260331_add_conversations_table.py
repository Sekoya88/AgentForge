"""Add conversations table

Revision ID: 20260331_conversations
Revises: beeb5ff46610
Create Date: 2026-03-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260331_conversations"
down_revision: str | None = "beeb5ff46610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id"),
    )
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_index(op.f("ix_conversations_agent_id"), "conversations", ["agent_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_conversations_agent_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_user_id"), table_name="conversations")
    op.drop_table("conversations")
