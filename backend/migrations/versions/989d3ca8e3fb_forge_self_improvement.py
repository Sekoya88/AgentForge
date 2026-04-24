"""forge_self_improvement

Revision ID: 989d3ca8e3fb
Revises: 20260420_forge_memory
Create Date: 2026-04-24 22:12:50.401271

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "989d3ca8e3fb"
down_revision: str | None = "20260420_forge_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- forge_sub_agent ---
    op.create_table(
        "forge_sub_agent",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("tools", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_forge_sub_agent_name", "forge_sub_agent", ["name"])
    op.create_index("ix_forge_sub_agent_user_id", "forge_sub_agent", ["user_id"])

    # --- execution_feedback ---
    op.create_table(
        "execution_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="other"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_execution_feedback_agent_id", "execution_feedback", ["agent_id"])
    op.create_index("ix_execution_feedback_user_id", "execution_feedback", ["user_id"])

    # --- meta_proposal ---
    op.create_table(
        "meta_proposal",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proposal_type", sa.String(50), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(20), nullable=False, server_default="on_demand"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_meta_proposal_user_id_status", "meta_proposal", ["user_id", "status"])

    # --- column additions ---
    op.add_column("executions", sa.Column("feedback_score", sa.Float(), nullable=True))
    op.add_column(
        "executions",
        sa.Column("feedback_category", sa.String(50), nullable=True),
    )
    op.add_column(
        "forge_conversations",
        sa.Column("meta_proposal_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("forge_conversations", "meta_proposal_id")
    op.drop_column("executions", "feedback_category")
    op.drop_column("executions", "feedback_score")
    op.drop_index("ix_meta_proposal_user_id_status", table_name="meta_proposal")
    op.drop_table("meta_proposal")
    op.drop_index("ix_execution_feedback_user_id", table_name="execution_feedback")
    op.drop_index("ix_execution_feedback_agent_id", table_name="execution_feedback")
    op.drop_table("execution_feedback")
    op.drop_index("ix_forge_sub_agent_user_id", table_name="forge_sub_agent")
    op.drop_index("ix_forge_sub_agent_name", table_name="forge_sub_agent")
    op.drop_table("forge_sub_agent")
