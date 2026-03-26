# backend/migrations/versions/008_indexes.py
"""Add missing indexes on high-query columns.

Revision ID: 008_indexes
Revises: 007
Create Date: 2026-03-26
"""

from alembic import op

revision = "008_indexes"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # executions: filter by agent, user, status (dashboard, list pages)
    op.create_index("ix_executions_agent_id", "executions", ["agent_id"], if_not_exists=True)
    op.create_index("ix_executions_user_id", "executions", ["user_id"], if_not_exists=True)
    op.create_index("ix_executions_status", "executions", ["status"], if_not_exists=True)
    op.create_index(
        "ix_executions_agent_started",
        "executions",
        ["agent_id", "started_at"],
        if_not_exists=True,
    )

    # campaigns: filter by agent, user, status
    op.create_index("ix_campaigns_agent_id", "campaigns", ["agent_id"], if_not_exists=True)
    op.create_index("ix_campaigns_user_id", "campaigns", ["user_id"], if_not_exists=True)
    op.create_index("ix_campaigns_status", "campaigns", ["status"], if_not_exists=True)

    # agents: filter by user (list page)
    op.create_index("ix_agents_user_id", "agents", ["user_id"], if_not_exists=True)
    op.create_index("ix_agents_status", "agents", ["status"], if_not_exists=True)

    # skills: filter by user, public
    op.create_index("ix_skills_user_id", "skills", ["user_id"], if_not_exists=True)
    op.create_index("ix_skills_is_public", "skills", ["is_public"], if_not_exists=True)

    # finetune_jobs: filter by user, status (resume on startup)
    op.create_index("ix_finetune_jobs_user_id", "finetune_jobs", ["user_id"], if_not_exists=True)
    op.create_index("ix_finetune_jobs_status", "finetune_jobs", ["status"], if_not_exists=True)

    # agent_versions: filter by agent (version history)
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"], if_not_exists=True)

    # knowledge_chunks: table uses user_id + source_title (already indexed in 004),
    # no knowledge_source_id FK column exists in this schema.


def downgrade() -> None:
    op.drop_index("ix_agent_versions_agent_id", table_name="agent_versions")
    op.drop_index("ix_finetune_jobs_status", table_name="finetune_jobs")
    op.drop_index("ix_finetune_jobs_user_id", table_name="finetune_jobs")
    op.drop_index("ix_skills_is_public", table_name="skills")
    op.drop_index("ix_skills_user_id", table_name="skills")
    op.drop_index("ix_agents_status", table_name="agents")
    op.drop_index("ix_agents_user_id", table_name="agents")
    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_index("ix_campaigns_user_id", table_name="campaigns")
    op.drop_index("ix_campaigns_agent_id", table_name="campaigns")
    op.drop_index("ix_executions_agent_started", table_name="executions")
    op.drop_index("ix_executions_status", table_name="executions")
    op.drop_index("ix_executions_user_id", table_name="executions")
    op.drop_index("ix_executions_agent_id", table_name="executions")
