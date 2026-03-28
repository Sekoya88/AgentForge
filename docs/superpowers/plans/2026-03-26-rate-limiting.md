# Rate Limiting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-IP and per-user rate limiting to the FastAPI backend to prevent brute-force attacks on auth endpoints and protect expensive LLM/GPU execution endpoints.

**Architecture:** Use `slowapi` (the FastAPI-compatible rate limiter backed by Redis or in-memory). Apply strict limits on `/api/v1/auth/login` and `/api/v1/auth/register` (brute-force protection), moderate limits on `/api/v1/agents/{id}/execute` and `/api/v1/sandbox/run` (expensive ops), and relaxed limits on everything else. Rate limit key: real client IP from `X-Forwarded-For` header (with proxy trust configured). In tests, use `fakeredis` or the default in-memory limiter.

**Tech Stack:** `slowapi>=0.1.9`, `limits` (transitive dependency), existing `app/main.py` FastAPI app, existing Redis connection.

---

### Task 1: Install and configure slowapi

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add slowapi to pyproject.toml**

In `backend/pyproject.toml`, add `"slowapi>=0.1.9"` to the `dependencies` list after `"redis[hiredis]>=5.2.0"`:

```toml
    "slowapi>=0.1.9",
```

- [ ] **Step 2: Install the dependency**

```bash
cd backend && uv pip install --system -e ".[dev]"
```

Expected: `slowapi` installed, no errors.

- [ ] **Step 3: Create `backend/app/api/middleware/rate_limit.py`**

```python
# backend/app/api/middleware/rate_limit.py
"""Shared Limiter instance — import this, never instantiate elsewhere."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
```

- [ ] **Step 4: Wire the limiter into `backend/app/main.py`**

Add the following imports after the existing imports in `main.py`:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.middleware.rate_limit import limiter
```

Then inside the existing `app = FastAPI(...)` block, add state and middleware. After the `app = FastAPI(...)` line and before the existing middleware adds, insert:

```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

And add `SlowAPIMiddleware` to the middleware stack (add it after the existing `app.add_middleware(CorrelationIdMiddleware)` line):

```python
app.add_middleware(SlowAPIMiddleware)
```

- [ ] **Step 5: Commit**

```bash
cd backend && git add pyproject.toml app/main.py app/api/middleware/rate_limit.py
git commit -m "feat(security): add slowapi rate limiter scaffold"
```

---

### Task 2: Rate-limit auth endpoints (brute-force protection)

**Files:**
- Modify: `backend/app/api/v1/auth.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/api/test_rate_limiting.py`:

```python
# backend/tests/api/test_rate_limiting.py
"""Rate limiting integration tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429_after_threshold(client: AsyncClient, alembic_ready):
    """Hammering /login with bad creds should eventually return 429."""
    payload = {"email": "nobody@example.com", "password": "wrong"}
    responses = []
    for _ in range(25):  # limit is 10/minute on login
        r = await client.post("/api/v1/auth/login", json=payload)
        responses.append(r.status_code)
    assert 429 in responses, f"Expected 429 in {set(responses)}"


@pytest.mark.asyncio
async def test_register_rate_limit_returns_429_after_threshold(client: AsyncClient, alembic_ready):
    """Hammering /register should eventually return 429."""
    responses = []
    for i in range(25):  # limit is 10/minute on register
        r = await client.post(
            "/api/v1/auth/register",
            json={"email": f"spam{i}@example.com", "password": "testpass123"},
        )
        responses.append(r.status_code)
    assert 429 in responses, f"Expected 429 in {set(responses)}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/api/test_rate_limiting.py -v
```

Expected: Tests FAIL (no rate limiting yet → 401/200 responses, never 429).

- [ ] **Step 3: Apply rate limit decorators to auth routes**

Modify `backend/app/api/v1/auth.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.api.middleware.rate_limit import limiter
from app.api.schemas.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.application.services.auth_service import AuthService
from app.dependencies import get_auth_service, get_current_user
from app.domain.entities.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/register", response_model=UserResponse)
@limiter.limit("10/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    return await svc.register(body.email, body.password, body.display_name)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    access, refresh, _ = await svc.login(body.email, body.password)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    access = svc.refresh(body.refresh_token)
    return TokenResponse(access_token=access, refresh_token=body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await svc.change_password(user.id, body.current_password, body.new_password)
```

Note: `slowapi` requires `request: Request` as the first parameter of rate-limited routes.

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/api/test_rate_limiting.py -v
```

Expected: Both PASS (429 appears after 10 requests from same IP).

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd backend && pytest -q --tb=short
```

Expected: All tests PASS. If existing auth tests fail because they hit the rate limit, add `@pytest.mark.asyncio` fixture to reset the limiter between tests — see Task 4.

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/api/v1/auth.py tests/api/test_rate_limiting.py
git commit -m "feat(security): rate-limit /auth/login and /register to 10/minute"
```

---

### Task 3: Rate-limit expensive execution endpoints

**Files:**
- Modify: `backend/app/api/v1/agents.py`
- Modify: `backend/app/api/v1/sandbox.py` (check exact filename: may be `sandbox.py` or included in another router)

- [ ] **Step 1: Find the sandbox router file**

```bash
ls backend/app/api/v1/
```

Note the filename for the sandbox router.

- [ ] **Step 2: Add rate limit to agent execute endpoint**

In `backend/app/api/v1/agents.py`, add to imports:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.api.middleware.rate_limit import limiter
```

Then add the decorator to `execute_agent`:

```python
@router.post("/{agent_id}/execute")
@limiter.limit("30/minute")
async def execute_agent(
    request: Request,
    agent_id: UUID,
    body: ExecuteAgentRequest,
    user: Annotated[User, Depends(get_current_user)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> JSONResponse:
    e = await svc.execute(
        agent_id,
        user.id,
        body.input_messages,
        run_async=body.run_async,
    )
    payload = jsonable_encoder(_exec_to_response(e))
    code = status.HTTP_202_ACCEPTED if body.run_async else status.HTTP_200_OK
    return JSONResponse(status_code=code, content=payload)
```

- [ ] **Step 3: Add rate limit to sandbox run endpoint**

Open the sandbox router file. Add to imports:

```python
from fastapi import Request
from app.api.middleware.rate_limit import limiter
```

Then decorate the `run` endpoint:

```python
@router.post("/run")
@limiter.limit("20/minute")
async def run_sandbox(
    request: Request,
    # ... existing params unchanged ...
):
```

- [ ] **Step 4: Run full test suite**

```bash
cd backend && pytest -q --tb=short
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/api/v1/agents.py app/api/v1/
git commit -m "feat(security): rate-limit execute (30/min) and sandbox/run (20/min)"
```

---

### Task 4: Fix existing tests that may now hit rate limits

**Files:**
- Modify: `backend/tests/conftest.py`

The rate limiter uses `get_remote_address` which defaults to `testclient` IP in httpx test client. Multiple tests hitting the same endpoint may trigger the limit. The fix is to reset the limiter's storage between tests.

- [ ] **Step 1: Check if any existing tests now fail**

```bash
cd backend && pytest -q --tb=short 2>&1 | grep -E "FAILED|429"
```

If no failures, skip to Step 3.

- [ ] **Step 2: Add limiter reset to conftest.py if needed**

In `backend/tests/conftest.py`, add after existing imports:

```python
from app.api.middleware.rate_limit import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate limit counters between tests."""
    limiter._storage.reset()
    yield
    limiter._storage.reset()
```

- [ ] **Step 3: Verify all tests pass**

```bash
cd backend && pytest -q --tb=short
```

Expected: All PASS, coverage ≥ 80%.

- [ ] **Step 4: Commit**

```bash
cd backend && git add tests/conftest.py
git commit -m "test(security): reset rate limiter storage between tests"
```
