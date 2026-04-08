"""Workspace-level rate limit middleware.

Current implementation: attaches ``X-RateLimit-User-Limit`` header to agent
execution responses so clients know the configured limit for the authenticated
workspace (user).

Architecture note — why enforcement is a stub
---------------------------------------------
``slowapi`` (backed by ``limits``) resolves rate-limit *strings* (e.g. "60/hour")
at decoration time, so limits cannot be read from the database per-request without
custom storage backends. Full per-workspace enforcement would require one of:

  1. A custom ``slowapi`` storage backend using Redis sorted sets
     (ZADD / ZREMRANGEBYSCORE / ZCARD) keyed by user_id + endpoint.
  2. Replacing the ``@limiter.limit(...)`` decorators on the execute endpoint
     with an explicit FastAPI dependency that performs the Redis check inline.

The infrastructure (``users.execution_rate_limit`` column, migration, settings
endpoint) is in place. Enforcement can be wired in a follow-up task once the
preferred Redis key schema is agreed upon.

Usage
-----
Register in ``app/main.py``::

    from app.api.middleware.workspace_rate_limit import workspace_rate_limit_middleware
    app.middleware("http")(workspace_rate_limit_middleware)
"""

from fastapi import Request

# Paths for which we surface the user's configured rate limit.
_EXECUTION_PATH_FRAGMENT = "/execute"


async def workspace_rate_limit_middleware(request: Request, call_next):
    """Attach ``X-RateLimit-User-Limit`` header to agent execution responses.

    The header value is the ``execution_rate_limit`` stored on the authenticated
    user's row (executions per hour). It is informational only — the actual
    request-count enforcement is handled by the IP-based slowapi limiter until
    the Redis sorted-set enforcement layer is implemented.
    """
    response = await call_next(request)

    # Only annotate execution endpoints to avoid the overhead on every request.
    if _EXECUTION_PATH_FRAGMENT in request.url.path:
        # The User object is not directly available in ASGI middleware (it lives
        # inside FastAPI's dependency injection layer). We use request.state if
        # a dependency has stashed it there; otherwise we skip the header rather
        # than issuing an extra DB query from middleware.
        user = getattr(request.state, "current_user", None)
        if user is not None:
            response.headers["X-RateLimit-User-Limit"] = str(user.execution_rate_limit)
            response.headers["X-RateLimit-User-Window"] = "3600"  # seconds (1 hour)

    return response
