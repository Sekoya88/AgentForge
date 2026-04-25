"""speech_examples + voice_samples (base64 MVP; prefer object storage at scale)

Revision ID: 015_speech_data
Revises: 014_social_accounts_oauth
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "015_speech_data"
down_revision = "014_social_accounts_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_samples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column(
            "audio_b64",
            sa.Text(),
            nullable=False,
            comment="MVP: base64 audio; large rows — move to object storage for production scale",
        ),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_voice_samples_user_id", "voice_samples", ["user_id"])

    op.create_table(
        "speech_examples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "execution_id",
            UUID(as_uuid=True),
            sa.ForeignKey("executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("audio_b64", sa.Text(), nullable=False),
        sa.Column(
            "transcription",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_speech_examples_user_id", "speech_examples", ["user_id"])
    op.create_index("ix_speech_examples_agent_id", "speech_examples", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_speech_examples_agent_id", table_name="speech_examples")
    op.drop_index("ix_speech_examples_user_id", table_name="speech_examples")
    op.drop_table("speech_examples")
    op.drop_index("ix_voice_samples_user_id", table_name="voice_samples")
    op.drop_table("voice_samples")
