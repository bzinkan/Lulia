"""
Migration: add dual-bucket credits to teachers table.

Adds `credits_purchased` column for one-time credit-pack purchases that never
expire. The existing `credit_balance` column continues to represent the
monthly subscription allotment that resets each billing cycle.

Spending order in charge_credits(): monthly first, then purchased.

Idempotent — safe to re-run.
"""
import logging
import sys

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def migrate():
    conn = get_connection()
    cur = conn.cursor()

    # Add credits_purchased if not present
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'teachers' AND column_name = 'credits_purchased'
    """)
    if cur.fetchone():
        log.info("teachers.credits_purchased already exists — skipping add")
    else:
        cur.execute("ALTER TABLE teachers ADD COLUMN credits_purchased INT NOT NULL DEFAULT 0")
        log.info("Added teachers.credits_purchased (default 0)")

    # Add clip_previews_used_this_month (6 free per month for Plus+ tiers, resets monthly)
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'teachers' AND column_name = 'clip_previews_used_this_month'
    """)
    if cur.fetchone():
        log.info("teachers.clip_previews_used_this_month already exists — skipping add")
    else:
        cur.execute("ALTER TABLE teachers ADD COLUMN clip_previews_used_this_month INT NOT NULL DEFAULT 0")
        log.info("Added teachers.clip_previews_used_this_month (default 0)")

    # Backfill: any existing Max tier teachers had "unlimited" (-1) credits.
    # Reset their monthly balance to the new 1500 cap so billing behaves consistently.
    cur.execute("""
        SELECT teacher_id, credit_balance, tier
        FROM teachers
        WHERE tier = 'max' AND (credit_balance IS NULL OR credit_balance < 1500)
    """)
    rows = cur.fetchall()
    for teacher_id, balance, tier in rows:
        log.info(f"Backfilling Max teacher {teacher_id}: balance {balance} -> 1500")
        cur.execute(
            "UPDATE teachers SET credit_balance = 1500 WHERE teacher_id = %s",
            (teacher_id,),
        )

    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Migration complete. {len(rows)} Max-tier teachers backfilled to 1500 monthly credits.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        log.error(f"Migration failed: {e}")
        sys.exit(1)
