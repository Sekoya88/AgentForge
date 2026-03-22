"""agent_versions — snapshot history for every agent PUT

Revision ID: 005
Revises: 004
Create Date: 2026-03-22

"""

from collections.abc import Sequence

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE agent_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    graph_definition JSONB NOT NULL,
    model_config    JSONB NOT NULL,
    skills          TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    change_note     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_id, version_number)
)
    """)
    op.execute("CREATE INDEX ix_agent_versions_agent_id ON agent_versions (agent_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_versions")
