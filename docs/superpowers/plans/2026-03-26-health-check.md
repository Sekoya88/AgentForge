# Enriched Health Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the trivial `GET /health` → `{"status": "ok"}` with a real health check that verifies DB connectivity and Redis connectivity. Returns `200` when healthy, `503` when degraded, suitable for Kubernetes liveness/readiness probes and load balancer health checks.

**Architecture:** The `/health` endpoint queries both Postgres (simple `SELECT 1`) and Redis (PING command) asynchronously. Returns `{"status": "ok"|"degraded", "checks": {"db": "ok"|"error", "redis": "ok"|"error"|"unavailable"}}`. If any check fails → HTTP 503. Redis failure returns `"unavailable"` (not a hard failure since some features degrade gracefully without Redis).

**Tech Stack:** FastAPI, SQLAlchemy async session, `redis.asyncio`.

---

### Task 1: Write the enriched health check

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_health_enriched.py`:

```python
# backend/tests/test_health_enriched.py
"""Health check tests verifying DB and Redis checks."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok_returns_200_with_checks(client: AsyncClient, alembic_ready):
    """Healthy system returns 200 with all checks passing."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "checks" in body
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["redis"] in ("ok", "unavailable")  # Redis may not be configured


@pytest.mark.asyncio
async def test_health_response_schema(client: AsyncClient, alembic_ready):
    """Response always has status and checks keys."""
    resp = await client.get("/health")
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    assert "db" in body["checks"]
    assert "redis" in body["checks"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_health_enriched.py -v
```

Expected: FAIL — current `/health` returns `{"status": "ok"}` without `checks` key.

- [ ] **Step 3: Replace the `/health` endpoint in `main.py`**

Remove the existing simple health endpoint and replace with:

```python
@app.get("/health")
async def health() -> dict:
    from sqlalchemy import text as sa_text

    from app.infrastructure.persistence.postgres.session import get_session_factory
    from app.infrastructure.redis_client import get_redis_client

    checks: dict[str, str] = {}

    # DB check
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(sa_text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # Redis check
    redis_client = get_redis_client()
    if redis_client is None:
        checks["redis"] = "unavailable"
    else:
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"

    overall = "ok" if all(v == "ok" for v in checks.values() if v != "unavailable") else "degraded"

    from fastapi import Response
    from fastapi.responses import JSONResponse
    status_code = 200 if overall == "ok" else 503
    return JSONResponse(content={"status": overall, "checks": checks}, status_code=status_code)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/test_health_enriched.py tests/test_health.py -v
```

Expected: All PASS (existing test_health.py tests still pass since we return 200 when healthy).

- [ ] **Step 5: Run full test suite**

```bash
cd backend && pytest -q --tb=short
```

Expected: All PASS, coverage ≥ 80%.

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/main.py tests/test_health_enriched.py
git commit -m "feat(ops): enriched /health with DB and Redis connectivity checks"
```
