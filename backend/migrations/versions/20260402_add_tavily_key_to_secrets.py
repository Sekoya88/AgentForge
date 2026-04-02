"""add tavily key to user secrets"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260402_tavily_key"
down_revision: str | Sequence[str] | None = "20260401_exec_compare"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_secrets", sa.Column("encrypted_tavily_key", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("user_secrets", "encrypted_tavily_key")
