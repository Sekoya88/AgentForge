"""executions.output_audio_b64

Revision ID: 012_output_audio_b64
Revises: 011_webhooks_modality
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012_output_audio_b64"
down_revision = "011_webhooks_modality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("output_audio_b64", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("executions", "output_audio_b64")
