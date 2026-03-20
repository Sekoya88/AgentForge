"""skills and finetune_jobs tables

Revision ID: 003
Revises: 002
Create Date: 2025-03-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("version", sa.String(20), server_default="1.0.0"),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("parameters_schema", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("permissions", ARRAY(sa.Text()), server_default=sa.text("ARRAY[]::text[]")),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("security_validated", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "finetune_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("base_model", sa.String(255), nullable=False),
        sa.Column("dataset_path", sa.String(500), nullable=False),
        sa.Column("hyperparams", JSONB, nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("modal_job_id", sa.String(255)),
        sa.Column("metrics", JSONB),
        sa.Column("model_output_path", sa.String(500)),
        sa.Column("inference_endpoint", sa.String(500)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("finetune_jobs")
    op.drop_table("skills")
