# backend/app/api/middleware/rate_limit.py
"""Shared Limiter instance — import this, never instantiate elsewhere.

`get_remote_address` keys limits by client IP. Auth routes (`/api/v1/auth/login`,
`/api/v1/auth/register`, …) apply stricter per-route `@limiter.limit(...)` decorators
in `api/v1/auth.py` on top of this default.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
