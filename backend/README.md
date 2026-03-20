# AgentForge Backend

FastAPI + SQLAlchemy 2 async + Alembic. Run locally with Docker Compose from repo root.

```bash
cd backend && uv pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Tests: `pytest`
