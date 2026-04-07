"""
Feature Flags — controls feature availability per teacher, tier, and rollout percentage.

Check order: teacher override → tier requirement → rollout % → default.
"""
import hashlib
import logging
import os
from psycopg2.extras import RealDictCursor
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


def is_feature_enabled(teacher_id: str, flag_key: str) -> bool:
    """Check if a feature is enabled for a specific teacher."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Check teacher override
    cur.execute(
        "SELECT enabled FROM teacher_feature_overrides WHERE teacher_id = %s::uuid AND flag_key = %s",
        (teacher_id, flag_key),
    )
    override = cur.fetchone()
    if override:
        cur.close(); conn.close()
        return override["enabled"]

    # 2. Get flag config
    cur.execute("SELECT * FROM feature_flags WHERE key = %s", (flag_key,))
    flag = cur.fetchone()
    if not flag:
        cur.close(); conn.close()
        return False

    # 3. Check tier requirement
    if flag.get("tier_required"):
        cur.execute(
            "SELECT COALESCE((SELECT tier FROM credit_accounts WHERE teacher_id = %s::uuid), 'basic') as tier",
            (teacher_id,),
        )
        tier = cur.fetchone()["tier"]
        tier_order = {"basic": 0, "plus": 1, "premium": 2, "max": 3}
        required_level = tier_order.get(flag["tier_required"], 0)
        teacher_level = tier_order.get(tier, 0)
        if teacher_level < required_level:
            cur.close(); conn.close()
            return False

    # 4. Check rollout percentage
    rollout = flag.get("rollout_percentage", 100)
    if rollout < 100:
        # Deterministic: same teacher always gets same result for same flag
        hash_val = int(hashlib.md5(f"{teacher_id}:{flag_key}".encode()).hexdigest()[:8], 16)
        if (hash_val % 100) >= rollout:
            cur.close(); conn.close()
            return False

    cur.close(); conn.close()
    return flag.get("default_enabled", False)


def get_teacher_features(teacher_id: str) -> dict[str, bool]:
    """Return all features and whether they're enabled for this teacher."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT key FROM feature_flags")
    flags = [r["key"] for r in cur.fetchall()]
    cur.close(); conn.close()

    return {key: is_feature_enabled(teacher_id, key) for key in flags}
