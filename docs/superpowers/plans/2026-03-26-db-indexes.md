# Database Indexes Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add missing database indexes on the most frequently queried columns to prevent full table scans at scale. The common query patterns are: filtering executions by agent_id/user_id/status, filtering campaigns by agent_id, filtering finetune jobs by status/user_id, and filtering skills by user_id.

**Architecture:** Single Alembic migration `008_indexes.py` adding `CREATE INDEX` for all critical columns. No data changes — pure DDL. Indexes are non-blocking in Postgres with `CREATE INDEX CONCURRENTLY`, but since Alembic runs in a transaction by default, we use regular `CREATE INDEX` (acceptable for a dev-stage migration) with a note for prod.

**Tech Stack:** Alembic, SQLAlchemy, PostgreSQL 16.

---

### Task 1: Audit existing indexes

**Files:**
- Read: `backend/migrations/versions/001_initial_schema.py` (and others)

- [ ] **Step 1: Check what indexes already exist**

```bash
cd backend && python -c "
from sqlalchemy import create_engine, inspect, text
import os
url = os.environ.get('DATABASE_URL', 'postgresql+psycopg2://forge:forge@localhost:5433/agentforge').replace('+asyncpg','').replace('+psycopg2','')
from sqlalchemy import create_engine
eng = create_engine(url)
with eng.connect() as conn:
    rows = conn.execute(text('''
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    ''')).fetchall()
    for r in rows: print(r)
"
```

Expected: Lists primary key indexes and any unique indexes. Note which foreign key columns lack indexes.

- [ ] **Step 2: Identify the last migration version**

```bash
ls backend/migrations/versions/ | sort
```

Note the highest number (e.g., `007_skill_type_instructions.py`). Next migration is `008`.

---

### Task 2: Create the indexes migration

**Files:**
- Create: `backend/migrations/versions/008_indexes.py`

- [ ] **Step 1: Get the current head revision**

```bash
cd backend && python -m alembic heads
```

Note the revision hash (e.g., `abc123def456`).

- [ ] **Step 2: Create `008_indexes.py`**

Replace `<prev_revision>` with the hash from Step 1:

```python
# backend/migrations/versions/008_indexes.py
"""Add missing indexes on high-query columns.

Revision ID: 008_indexes
Revises: <prev_revision>
Create Date: 2026-03-26
"""
from alembic import op

revision = "008_indexes"
down_revision = "<prev_revision>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # executions: filter by agent, user, status (dashboard, list pages)
    op.create_index("ix_executions_agent_id", "executions", ["agent_id"])
    op.create_index("ix_executions_user_id", "executions", ["user_id"])
    op.create_index("ix_executions_status", "executions", ["status"])
    op.create_index(
        "ix_executions_agent_started",
        "executions",
        ["agent_id", "started_at"],
    )

    # campaigns: filter by agent, user, status
    op.create_index("ix_campaigns_agent_id", "campaigns", ["agent_id"])
    op.create_index("ix_campaigns_user_id", "campaigns", ["user_id"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])

    # agents: filter by user (list page)
    op.create_index("ix_agents_user_id", "agents", ["user_id"])
    op.create_index("ix_agents_status", "agents", ["status"])

    # skills: filter by user, public
    op.create_index("ix_skills_user_id", "skills", ["user_id"])
    op.create_index("ix_skills_is_public", "skills", ["is_public"])

    # finetune_jobs: filter by user, status (resume on startup)
    op.create_index("ix_finetune_jobs_user_id", "finetune_jobs", ["user_id"])
    op.create_index("ix_finetune_jobs_status", "finetune_jobs", ["status"])

    # agent_versions: filter by agent (version history)
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])

    # knowledge_chunks: filter by source (search)
    op.create_index(
        "ix_knowledge_chunks_source_id", "knowledge_chunks", ["knowledge_source_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_source_id", table_name="knowledge_chunks")
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
```

Note: Replace `knowledge_source_id` with the actual FK column name if different. Check `backend/app/infrastructure/persistence/postgres/models.py` for the exact column name on `knowledge_chunks`.

- [ ] **Step 3: Fix the `knowledge_chunks` column name if needed**

```bash
grep -n "knowledge_source_id\|source_id\|ForeignKey" backend/app/infrastructure/persistence/postgres/models.py | grep -i chunk
```

Adjust `ix_knowledge_chunks_source_id` index definition to use the actual column name.

- [ ] **Step 4: Run the migration**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5433/agentforge python -m alembic upgrade head
```

Expected: Migration applies without errors.

- [ ] **Step 5: Verify indexes exist**

```bash
cd backend && python -c "
from sqlalchemy import create_engine, text
eng = create_engine('postgresql://forge:forge@localhost:5433/agentforge')
with eng.connect() as conn:
    rows = conn.execute(text(\"SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'ix_%' ORDER BY tablename\")).fetchall()
    for r in rows: print(r)
"
```

Expected: All `ix_*` indexes listed.

- [ ] **Step 6: Commit**

```bash
cd backend && git add migrations/versions/008_indexes.py
git commit -m "feat(db): add indexes on high-query columns (executions, agents, campaigns, skills, finetune_jobs)"
```

---

### Task 3: Verify tests still pass with the new migration

- [ ] **Step 1: Run full test suite**

```bash
cd backend && pytest -q --tb=short
```

Expected: All PASS (indexes are transparent to query logic).

- [ ] **Step 2: If any test fails due to a duplicate index error**

Some columns might already have indexes from ForeignKey constraints. If `alembic upgrade` failed with "already exists", add `if_not_exists=True` to those specific `create_index` calls:

```python
op.create_index("ix_executions_agent_id", "executions", ["agent_id"], if_not_exists=True)
```

Repeat for any failing index, then re-run migration and tests.
