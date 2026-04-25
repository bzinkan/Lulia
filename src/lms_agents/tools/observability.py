"""
observability.py — structured logging + request-ID correlation for FastAPI.

Why this exists:
    - Pre-AWS the app logged unstructured text to stderr with no request IDs,
      making CloudWatch debugging painful. This module wires in JSON logs with
      a request_id field that every log call in a request gets for free.
    - Also exposes a single ExceptionHandler so stack traces never leak to
      clients in prod, while still logging full traces server-side.

Usage (main.py):

    from src.lms_agents.tools.observability import (
        configure_logging, RequestIdMiddleware, register_exception_handlers,
    )

    configure_logging()  # before app = FastAPI(...)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

Consumers log normally with `logging.getLogger(__name__)` — the contextvar
propagates request_id into each record automatically.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


# Contextvar is propagated across awaits, so any logger call inside a request
# sees the same request_id without plumbing it through every function.
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """Return the request_id for the active request, or None outside a request."""
    return _request_id_var.get()


class _RequestIdFilter(logging.Filter):
    """Attaches request_id to every LogRecord so the formatter can include it."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = _request_id_var.get() or "-"
        return True


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter. CloudWatch-friendly, no deps."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        # Include any extra keys passed via logger.info(..., extra={...}).
        reserved = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message", "module",
            "msecs", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName",
            "request_id",
        }
        for k, v in record.__dict__.items():
            if k not in reserved and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str | None = None) -> None:
    """Install JSON formatter on the root logger.

    Call once at process start. Idempotent — re-running swaps the handler list.
    In dev (LOG_FORMAT=text), falls back to human-readable output so `docker
    compose logs` stays readable.
    """
    level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    fmt = os.environ.get("LOG_FORMAT", "json").lower()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    if fmt == "text":
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        ))
    else:
        handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Quiet noisy libs that would otherwise flood logs.
    for noisy in ("uvicorn.access", "httpx", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign each request a unique request_id + log duration/status.

    Reuses an inbound `X-Request-ID` header when present so multi-hop traces
    stay correlated across the dashboard -> API boundary.
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = _request_id_var.set(rid)
        log = logging.getLogger("request")
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Let the global exception handler format the JSON body; we still
            # log duration + stack for prod triage.
            dur_ms = (time.perf_counter() - start) * 1000
            log.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(dur_ms, 1),
                },
            )
            _request_id_var.reset(token)
            raise
        dur_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = rid
        # Skip noise on health checks — don't bury real logs.
        if request.url.path not in ("/health", "/ready"):
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(dur_ms, 1),
                },
            )
        _request_id_var.reset(token)
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Install a global handler so unexpected exceptions return safe JSON.

    FastAPI's default returns a plain 500 with internal details. In prod we want
    a consistent `{error, request_id}` shape that the dashboard can surface to
    teachers ("support reference: <id>").
    """

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):  # type: ignore[unused-variable]
        rid = current_request_id() or "-"
        logging.getLogger("error").error(
            "unhandled_exception",
            extra={
                "path": request.url.path,
                "method": request.method,
                "exc_type": exc.__class__.__name__,
                "exc_msg": str(exc),
                "stack": traceback.format_exc(),
            },
        )
        # Only include the message in non-prod so devs can see the cause.
        show_detail = os.environ.get("ENV", "dev").lower() in ("dev", "local", "test")
        body: dict[str, Any] = {
            "error": "internal_error",
            "request_id": rid,
        }
        if show_detail:
            body["detail"] = f"{exc.__class__.__name__}: {exc}"
        return JSONResponse(status_code=500, content=body)
