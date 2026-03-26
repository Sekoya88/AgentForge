# backend/app/api/middleware/rate_limit.py
"""Shared Limiter instance — import this, never instantiate elsewhere."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
