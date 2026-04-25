"""social_accounts + nullable user password for OAuth-only users

Revision ID: 014_social_accounts_oauth
Revises: 013_agent_schedules
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "014_social_accounts_oauth"
down_revision = "013_agent_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(255), nullable=True)
    op.create_table(
        "social_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("access_token_cipher", sa.Text(), nullable=True),
        sa.Column("refresh_token_cipher", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_social_accounts_user_id", "social_accounts", ["user_id"])
    op.create_unique_constraint(
        "uq_social_accounts_provider_provider_id",
        "social_accounts",
        ["provider", "provider_id"],
    )
    op.create_unique_constraint(
        "uq_social_accounts_user_provider",
        "social_accounts",
        ["user_id", "provider"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_social_accounts_user_provider", "social_accounts", type_="unique")
    op.drop_constraint("uq_social_accounts_provider_provider_id", "social_accounts", type_="unique")
    op.drop_index("ix_social_accounts_user_id", table_name="social_accounts")
    op.drop_table("social_accounts")
    op.alter_column("users", "hashed_password", existing_type=sa.String(255), nullable=False)
