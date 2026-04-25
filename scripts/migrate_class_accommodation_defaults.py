"""
Migration: add `default_accommodations` to `classes`.

Why:
    The planner refiner currently asks the teacher to tick IEP / 504 / ELL /
    Gifted on every work order, every day. A class that needs ELL-Beginner
    accommodations needs them every lesson, and nagging the teacher into
    that click is friction with no pedagogic value.

    `default_accommodations` is a JSONB array of accommodation ids that the
    refiner preselects when a work order has no accommodations of its own.
    The teacher can still override per-work-order (unchecking them on this
    particular lesson) — the default is just the initial state.

Idempotent — safe to re-run.
"""
from __future__ import annotations

import logging

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def migrate() -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "ALTER TABLE classes "
            "ADD COLUMN IF NOT EXISTS default_accommodations JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        # Sanity: any NULLs from an earlier attempt get flattened to [] so the
        # NOT NULL default sticks. (NOT NULL + default via ADD COLUMN already
        # handles this on fresh rows; this is belt-and-suspenders for envs
        # where the column existed previously without the constraint.)
        cur.execute(
            "UPDATE classes SET default_accommodations = '[]'::jsonb "
            "WHERE default_accommodations IS NULL"
        )
        conn.commit()
        log.info("[Migration] classes.default_accommodations ready")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    migrate()
