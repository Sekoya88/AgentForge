"""execution_policy on agents + versions; agent_version_number on executions; skill hash.

Revision ID: 009
Revises: 008_indexes
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009"
down_revision: str | None = "008_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE agents
        ADD COLUMN IF NOT EXISTS execution_policy JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE agent_versions
        ADD COLUMN IF NOT EXISTS execution_policy JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE executions
        ADD COLUMN IF NOT EXISTS agent_version_number INTEGER NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_executions_agent_version
        ON executions (agent_id, agent_version_number)
        """
    )
    op.execute(
        """
        ALTER TABLE skills
        ADD COLUMN IF NOT EXISTS source_sha256 VARCHAR(64) NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE skills DROP COLUMN IF EXISTS source_sha256")
    op.execute("DROP INDEX IF EXISTS ix_executions_agent_version")
    op.execute("ALTER TABLE executions DROP COLUMN IF EXISTS agent_version_number")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS execution_policy")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS execution_policy")
