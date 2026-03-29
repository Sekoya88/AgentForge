"""add_agent_id_to_finetune_jobs

Revision ID: 856e8f968224
Revises: 06094493e084
Create Date: 2026-03-29 15:54:30.588004

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "856e8f968224"
down_revision: str | None = "06094493e084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("finetune_jobs", sa.Column("agent_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        None, "finetune_jobs", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint(None, "finetune_jobs", type_="foreignkey")
    op.drop_column("finetune_jobs", "agent_id")
