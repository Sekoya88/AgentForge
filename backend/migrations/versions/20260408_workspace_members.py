"""add workspace_members table for role-based agent access

Revision ID: 20260408_workspace_members
Revises: 20260408_audio_url
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260408_workspace_members"
down_revision = "20260408_audio_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "member_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("invited_email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="viewer"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # Prevent duplicate invitations for the same email in the same workspace
    op.create_unique_constraint(
        "uq_workspace_member_email",
        "workspace_members",
        ["workspace_owner_id", "invited_email"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_workspace_member_email", "workspace_members", type_="unique")
    op.drop_table("workspace_members")
