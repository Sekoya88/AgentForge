"""delete_echo_registry_test_skills

Revision ID: 292a0fd1cbc6
Revises: 016_speech_optin
Create Date: 2026-03-31 21:52:13.143344

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "292a0fd1cbc6"
down_revision: str | None = "016_speech_optin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM skills WHERE name = 'public_echo_registry'")


def downgrade() -> None:
    pass
