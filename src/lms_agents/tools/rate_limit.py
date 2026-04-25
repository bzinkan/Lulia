"""Shared rate-limiter wiring for FastAPI endpoints.

Why a wrapper:
    slowapi's `Limiter` must be instantiated exactly once and attached to the
    FastAPI app's state so every router that decorates an endpoint with
    `@limiter.limit(...)` sees the same instance. Importing a module-level
    `limiter` here gives every router a shared handle while keeping the
    initialization logic (Redis vs. in-memory, env-driven disable, key
    function) in one place.

Storage:
    - Default: in-memory (per-process). Fine on a single task for dev + MVP.
    - Set RATE_LIMIT_STORAGE_URI=redis://host:6379 in prod so all Fargate
      tasks share counters. Otherwise a busy attacker just sprays across
      tasks and bypasses the limit.

Key function:
    - If an authenticated teacher is on the request (future), prefer
      `teacher:{id}`. For now we key on client IP, trusting X-Forwarded-For
      when behind ALB.

Disable switch:
    - RATE_LIMIT_ENABLED=false turns all limits off (useful for load tests
      and local dev where hammering your own API is fine).
"""
from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _client_key(request: Request) -> str:
    # Prefer the left-most X-Forwarded-For when behind ALB (the client IP).
    # Falls back to the direct peer IP otherwise.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


def _storage_uri() -> str:
    # slowapi uses the `limits` lib; "memory://" is the in-process default.
    return os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://")


_enabled = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"

limiter = Limiter(
    key_func=_client_key,
    storage_uri=_storage_uri(),
    enabled=_enabled,
    # Global default — any endpoint NOT explicitly decorated still gets a
    # generous cap so a runaway client can't melt an un-annotated route.
    default_limits=["600/minute"],
)


__all__ = ["limiter", "RateLimitExceeded"]
