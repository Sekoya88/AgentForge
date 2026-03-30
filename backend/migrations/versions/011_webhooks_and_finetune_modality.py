"""webhook_subscriptions + finetune_jobs.modality

Revision ID: 011_webhooks_modality
Revises: 856e8f968224
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "011_webhooks_modality"
down_revision = "856e8f968224"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "finetune_jobs",
        sa.Column(
            "modality",
            sa.String(length=32),
            nullable=False,
            server_default="text_sft",
        ),
    )

    op.create_table(
        "webhook_subscriptions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "events",
            JSONB,
            nullable=False,
            server_default=sa.text("'[\"execution.completed\"]'::jsonb"),
        ),
        sa.Column("secret", sa.String(length=512), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_webhook_subscriptions_user_id",
        "webhook_subscriptions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_subscriptions_user_id", table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
    op.drop_column("finetune_jobs", "modality")
