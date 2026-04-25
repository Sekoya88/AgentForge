"""hybrid search using tsvector and hnsw

Revision ID: 20260405_hybrid_search
Revises: 20260403_hf_elevenlabs_keys
Create Date: 2026-04-05

"""

from alembic import op

revision = "20260405_hybrid_search"
down_revision = "20260403_hf_elevenlabs_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add search_vector generated column to knowledge_chunks
    op.execute("""
        ALTER TABLE knowledge_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english', coalesce(content, ''))
        ) STORED;
    """)

    # 2. Create GIN index for search_vector
    op.execute("CREATE INDEX ix_knowledge_chunks_fts ON knowledge_chunks USING gin(search_vector);")

    # 3. Create HNSW index for fast vector search
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_embedding_hnsw
        ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_fts;")
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS search_vector;")
