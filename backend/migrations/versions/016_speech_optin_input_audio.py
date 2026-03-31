"""Opt-in speech example collection + persist input audio for /execute/audio.

Revision ID: 016_speech_optin
Revises: 015_speech_data
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "016_speech_optin"
down_revision = "015_speech_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "collect_speech_examples",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "collect_speech_examples",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("executions", sa.Column("input_audio_b64", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("executions", "input_audio_b64")
    op.drop_column("agents", "collect_speech_examples")
    op.drop_column("users", "collect_speech_examples")
