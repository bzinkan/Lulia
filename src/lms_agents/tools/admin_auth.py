"""
Super Admin Authentication — gates admin-only endpoints.

Checks the requesting user's email against SUPER_ADMIN_EMAILS env var.
Logs every admin action to admin_audit_log.

Session storage
---------------
Sessions live in Redis keyed by token, with a TTL that matches the logical
expiry (8h for admin, 30min for impersonation). This was previously an
in-process dict, which broke the moment you ran more than one API task
behind a load balancer — a token minted on task A would fail validation
on task B.

Redis + TTL gives us three wins over the dict:
  1. Tokens are shared across Fargate tasks.
  2. Expiry is handled by Redis (one less code path to own).
  3. Graceful shutdown / crash = sessions survive a restart, so an admin
     mid-investigation doesn't get bounced on a deploy.

Fallback
--------
If Redis is unreachable (e.g. local dev with the redis container stopped),
we fall back to an in-process dict with the same API. The fallback is
intentionally silent in dev but logs a WARNING every time it's hit — so
if prod ever falls through, it shows up in CloudWatch.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import Header, HTTPException
from psycopg2.extras import Json

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session store — Redis with in-process fallback
# ---------------------------------------------------------------------------

_ADMIN_SESSION_TTL = 8 * 60 * 60       # 8 hours
_IMPERSONATION_TTL = 30 * 60           # 30 minutes
_ADMIN_PREFIX = "admin:session:"
_IMPERSONATION_PREFIX = "admin:impersonate:"

_fallback_admin: dict[str, dict] = {}
_fallback_impersonation: dict[str, dict] = {}
_fallback_lock = threading.Lock()


def _redis_or_none():
    """Return the shared redis.Redis client, or None if construction fails.

    We deliberately do NOT ping — that would be an extra RTT on every admin
    request. The individual store/load/delete helpers wrap the actual
    Redis op in try/except, so a connection drop mid-request surfaces as a
    clean fallback to the in-process dict rather than a 500.
    """
    try:
        from src.lms_agents.tools.redis_client import get_redis
        return get_redis()
    except Exception as e:  # pragma: no cover — only on import/env failure
        log.warning("admin_auth: Redis client unavailable (%s) — using fallback", e)
        return None


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _fallback_set(fallback: dict[str, dict], token: str, payload: dict, ttl_seconds: int) -> None:
    with _fallback_lock:
        fallback[token] = {
            **payload,
            "__expires_at": (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat(),
        }


def _fallback_get(fallback: dict[str, dict], token: str) -> dict | None:
    with _fallback_lock:
        session = fallback.get(token)
        if not session:
            return None
        try:
            expires = datetime.fromisoformat(session["__expires_at"])
        except Exception:
            del fallback[token]
            return None
        if datetime.utcnow() > expires:
            del fallback[token]
            return None
        # Strip the fallback-only bookkeeping key so the caller gets a clean
        # dict that's identical in shape to what Redis would return.
        return {k: v for k, v in session.items() if k != "__expires_at"}


def _fallback_delete(fallback: dict[str, dict], token: str) -> None:
    with _fallback_lock:
        fallback.pop(token, None)


def _store_session(prefix: str, token: str, payload: dict, ttl_seconds: int,
                   fallback: dict[str, dict]) -> None:
    """Write `payload` under the prefixed token with the given TTL."""
    redis_client = _redis_or_none()
    if redis_client is not None:
        try:
            # JSON-serialize with default=str so datetime objects round-trip.
            redis_client.setex(f"{prefix}{token}", ttl_seconds, json.dumps(payload, default=str))
            return
        except Exception as e:
            log.warning("admin_auth: Redis setex failed (%s) — using fallback", e)
    _fallback_set(fallback, token, payload, ttl_seconds)


def _load_session(prefix: str, token: str,
                  fallback: dict[str, dict]) -> dict | None:
    """Return the session dict for `token`, or None if missing/expired."""
    redis_client = _redis_or_none()
    if redis_client is not None:
        try:
            raw = redis_client.get(f"{prefix}{token}")
        except Exception as e:
            log.warning("admin_auth: Redis get failed (%s) — using fallback", e)
            return _fallback_get(fallback, token)
        if not raw:
            # Not in Redis — but maybe we wrote it to the fallback during a
            # prior Redis outage. Check the fallback too. This is belt-and-
            # suspenders for the edge case where Redis briefly went down,
            # the session got written locally, Redis came back up, and now
            # we're looking up the token that never made it across.
            return _fallback_get(fallback, token)
        try:
            return json.loads(raw)
        except Exception:
            # Corrupt payload — evict so we don't keep blocking the admin.
            try:
                redis_client.delete(f"{prefix}{token}")
            except Exception:
                pass
            return None
    return _fallback_get(fallback, token)


def _delete_session(prefix: str, token: str, fallback: dict[str, dict]) -> None:
    redis_client = _redis_or_none()
    if redis_client is not None:
        try:
            redis_client.delete(f"{prefix}{token}")
        except Exception as e:
            log.warning("admin_auth: Redis delete failed (%s) — fallback-only delete", e)
    _fallback_delete(fallback, token)


# ---------------------------------------------------------------------------
# Super-admin primitives
# ---------------------------------------------------------------------------

def get_super_admin_emails() -> list[str]:
    """Get list of super admin emails from env."""
    raw = os.environ.get("SUPER_ADMIN_EMAILS", "")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


def is_super_admin(email: str) -> bool:
    """Check if an email is a super admin."""
    return email.strip().lower() in get_super_admin_emails()


def create_admin_session(email: str) -> str:
    """Create a short-lived admin session token."""
    token = str(uuid4())
    _store_session(
        _ADMIN_PREFIX,
        token,
        {"email": email, "created_at": _now_iso()},
        _ADMIN_SESSION_TTL,
        _fallback_admin,
    )
    return token


def validate_admin_token(token: str) -> dict | None:
    """Validate an admin session token. Returns the session dict or None."""
    return _load_session(_ADMIN_PREFIX, token, _fallback_admin)


def revoke_admin_session(token: str) -> None:
    """Explicitly revoke an admin token (logout path)."""
    _delete_session(_ADMIN_PREFIX, token, _fallback_admin)


def require_admin(x_admin_token: str = Header(None, alias="X-Admin-Token")) -> dict:
    """FastAPI dependency — require super admin authentication."""
    if not x_admin_token:
        raise HTTPException(status_code=401, detail="Admin token required")
    session = validate_admin_token(x_admin_token)
    if not session:
        raise HTTPException(status_code=403, detail="Invalid or expired admin token")
    return session


def log_admin_action(
    admin_email: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
):
    """Log an admin action to the audit log."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO admin_audit_log
               (log_id, admin_email, action, target_type, target_id, metadata, ip_address)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (str(uuid4()), admin_email, action, target_type, target_id,
             Json(metadata or {}), ip_address),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.warning(f"Failed to log admin action: {e}")
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Impersonation
# ---------------------------------------------------------------------------

def create_impersonation_token(admin_email: str, teacher_id: str) -> str:
    """Create a short-lived impersonation token."""
    token = f"imp_{uuid4()}"
    _store_session(
        _IMPERSONATION_PREFIX,
        token,
        {
            "admin_email": admin_email,
            "teacher_id": teacher_id,
            "created_at": _now_iso(),
        },
        _IMPERSONATION_TTL,
        _fallback_impersonation,
    )
    log_admin_action(admin_email, "impersonate_start", "teacher", teacher_id)
    return token


def validate_impersonation(token: str) -> dict | None:
    """Validate an impersonation token."""
    return _load_session(_IMPERSONATION_PREFIX, token, _fallback_impersonation)


def end_impersonation(token: str) -> None:
    """End an impersonation session."""
    session = validate_impersonation(token)
    _delete_session(_IMPERSONATION_PREFIX, token, _fallback_impersonation)
    if session:
        log_admin_action(
            session["admin_email"], "impersonate_end",
            "teacher", session.get("teacher_id"),
        )


# Backwards-compat aliases: some callers previously imported the bare dicts
# directly. Route those reads through the proper accessors so nothing breaks
# during a transitional commit. Prefer the explicit functions above.
_admin_sessions: dict[str, Any] = _fallback_admin  # noqa: N816 — legacy name
_impersonation_tokens: dict[str, Any] = _fallback_impersonation  # noqa: N816
