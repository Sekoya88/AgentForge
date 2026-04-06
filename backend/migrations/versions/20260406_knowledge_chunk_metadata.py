"""Add chunk_type and heading_context columns to knowledge_chunks

Revision ID: 20260406_knowledge_chunk_metadata
Revises: 20260405_hybrid_search
Create Date: 2026-04-06

Adds structural metadata columns inspired by memvid's structure-aware chunking:
- chunk_type: 'paragraph' | 'code' | 'table' | 'heading'
- heading_context: nearest ancestor heading text (propagated from chunker)

Both columns are nullable with defaults so existing rows are unaffected.
"""

from alembic import op

revision = "20260406_chunk_meta"
down_revision = "20260405_hybrid_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE knowledge_chunks
        ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(32) NOT NULL DEFAULT 'paragraph',
        ADD COLUMN IF NOT EXISTS heading_context TEXT NOT NULL DEFAULT '';
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS heading_context;")
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS chunk_type;")
