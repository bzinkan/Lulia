"""
Super Admin Authentication — gates admin-only endpoints.

Checks the requesting user's email against SUPER_ADMIN_EMAILS env var.
Logs every admin action to admin_audit_log.
"""
import os
import logging
from uuid import uuid4
from datetime import datetime, timedelta

from fastapi import Header, HTTPException
from psycopg2.extras import Json

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

# Simple token-based admin sessions (stored in memory for MVP)
_admin_sessions: dict[str, dict] = {}


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
    _admin_sessions[token] = {
        "email": email,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(hours=8),
    }
    return token


def validate_admin_token(token: str) -> dict | None:
    """Validate an admin session token."""
    session = _admin_sessions.get(token)
    if not session:
        return None
    if datetime.now() > session["expires_at"]:
        del _admin_sessions[token]
        return None
    return session


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


# --- Impersonation ---

_impersonation_tokens: dict[str, dict] = {}


def create_impersonation_token(admin_email: str, teacher_id: str) -> str:
    """Create a short-lived impersonation token."""
    token = f"imp_{uuid4()}"
    _impersonation_tokens[token] = {
        "admin_email": admin_email,
        "teacher_id": teacher_id,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(minutes=30),
    }
    log_admin_action(admin_email, "impersonate_start", "teacher", teacher_id)
    return token


def validate_impersonation(token: str) -> dict | None:
    """Validate an impersonation token."""
    session = _impersonation_tokens.get(token)
    if not session or datetime.now() > session["expires_at"]:
        return None
    return session


def end_impersonation(token: str):
    """End an impersonation session."""
    session = _impersonation_tokens.pop(token, None)
    if session:
        log_admin_action(session["admin_email"], "impersonate_end", "teacher", session["teacher_id"])
