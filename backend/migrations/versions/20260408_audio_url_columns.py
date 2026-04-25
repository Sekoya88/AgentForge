"""add audio_url columns for S3 object storage migration

Revision ID: 20260408_audio_url
Revises: add_health_score
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op

revision = "20260408_audio_url"
down_revision = "add_health_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # voice_samples: add audio_url, make audio_b64 nullable
    op.add_column("voice_samples", sa.Column("audio_url", sa.Text(), nullable=True))
    op.alter_column("voice_samples", "audio_b64", existing_type=sa.Text(), nullable=True)

    # speech_examples: add audio_url, make audio_b64 nullable
    op.add_column("speech_examples", sa.Column("audio_url", sa.Text(), nullable=True))
    op.alter_column("speech_examples", "audio_b64", existing_type=sa.Text(), nullable=True)

    # executions: add input_audio_url and output_audio_url
    op.add_column("executions", sa.Column("input_audio_url", sa.Text(), nullable=True))
    op.add_column("executions", sa.Column("output_audio_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("executions", "output_audio_url")
    op.drop_column("executions", "input_audio_url")

    op.alter_column("speech_examples", "audio_b64", existing_type=sa.Text(), nullable=False)
    op.drop_column("speech_examples", "audio_url")

    op.alter_column("voice_samples", "audio_b64", existing_type=sa.Text(), nullable=False)
    op.drop_column("voice_samples", "audio_url")
