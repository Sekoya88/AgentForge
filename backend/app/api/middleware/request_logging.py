"""Structured request access logs (structlog JSON)."""

import time
from collections.abc import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger(__name__)


def _skip_access_log(request: Request) -> bool:
    path = request.url.path
    if path == "/health":
        return True
    if path in ("/openapi.json", "/docs", "/redoc"):
        return True
    if path.startswith("/docs/"):
        return True
    return False


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs one line per request after response (method, path, status, ms, correlation_id)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if _skip_access_log(request):
            return await call_next(request)

        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            cid = getattr(request.state, "correlation_id", None)
            log.warning(
                "http_request_error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                correlation_id=cid,
            )
            raise

        duration_ms = int((time.perf_counter() - t0) * 1000)
        cid = getattr(request.state, "correlation_id", None)
        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            correlation_id=cid,
        )
        return response
