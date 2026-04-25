"""
One-time-ish helper: if this DB has never seen Alembic, stamp it at the
baseline revision so future `alembic upgrade head` runs work from here on.

Why this exists:
    We're introducing Alembic to an already-populated Lulia database. If
    we just ran `alembic upgrade head` cold, Alembic would see no
    `alembic_version` table, assume the DB is empty, and try to re-apply
    the entire revision chain — including any future revision that ALTERs
    a table that already has the change. Bad.

    The fix: `alembic stamp 0000_baseline` on first boot. This creates the
    `alembic_version` table and marks the baseline as applied WITHOUT
    running any SQL. Every revision authored after today stacks on top.

    Running this twice is safe — if we've already stamped (or upgraded
    past the baseline), we do nothing.

Usage:
    docker compose exec api python scripts/alembic_stamp_baseline.py
    (also run from FastAPI startup when AUTO_MIGRATE is enabled)
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def _has_alembic_version_table() -> bool:
    """Return True if alembic_version exists and is populated."""
    try:
        from src.lms_agents.tools.db import get_connection
    except ImportError:
        return False
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT EXISTS (
                 SELECT 1 FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_name = 'alembic_version'
               )"""
        )
        exists = bool(cur.fetchone()[0])
        if not exists:
            cur.close()
            return False
        # Table exists — is it populated?
        cur.execute("SELECT COUNT(*) FROM alembic_version")
        n = int(cur.fetchone()[0])
        cur.close()
        return n > 0
    finally:
        conn.close()


def stamp_baseline_if_needed() -> dict:
    """If the DB has no alembic_version entry yet, stamp it to the baseline.

    Returns a dict describing what happened: {"action": "stamped|skipped|error", ...}.
    Never raises — callers should tolerate a missing Alembic install as a
    soft failure (log + continue), so API boot isn't blocked.
    """
    try:
        already = _has_alembic_version_table()
    except Exception as e:
        log.error("[alembic-stamp] Could not inspect DB: %s", e)
        return {"action": "error", "detail": str(e)}

    if already:
        return {"action": "skipped", "reason": "alembic_version already present"}

    project_root = Path(__file__).parent.parent
    log.info("[alembic-stamp] stamping DB at baseline (0000_baseline)")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "stamp", "0000_baseline"],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"action": "error", "detail": "alembic stamp timed out"}
    except FileNotFoundError as e:
        return {"action": "error", "detail": f"alembic not found: {e}"}

    if result.returncode != 0:
        err = (result.stderr or result.stdout).strip()
        log.error("[alembic-stamp] stamp failed: %s", err[:500])
        return {"action": "error", "detail": err[:500]}

    return {"action": "stamped", "output": result.stdout.strip()}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    r = stamp_baseline_if_needed()
    print(r)
    sys.exit(0 if r["action"] != "error" else 1)
