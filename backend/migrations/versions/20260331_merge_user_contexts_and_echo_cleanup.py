"""merge user_contexts branch with echo_registry cleanup branch

Revision ID: 20260331_merge_v2_heads
Revises: 20260331_user_contexts, 292a0fd1cbc6
Create Date: 2026-03-31

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260331_merge_v2_heads"
down_revision: str | Sequence[str] | None = ("20260331_user_contexts", "292a0fd1cbc6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
