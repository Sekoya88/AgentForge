"""Add hf_token and elevenlabs_key columns to user_secrets.

Revision ID: 20260403_hf_elevenlabs_keys
Revises: previous
"""

import sqlalchemy as sa
from alembic import op

revision = "20260403_hf_elevenlabs_keys"
down_revision = "20260402_forge_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add HF token column (nullable, optional)
    op.add_column(
        "user_secrets",
        sa.Column("encrypted_hf_token", sa.String(512), nullable=True),
    )
    # Add ElevenLabs key column (nullable, optional)
    op.add_column(
        "user_secrets",
        sa.Column("encrypted_elevenlabs_key", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_secrets", "encrypted_elevenlabs_key")
    op.drop_column("user_secrets", "encrypted_hf_token")
