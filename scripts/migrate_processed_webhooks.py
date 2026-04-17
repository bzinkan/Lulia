"""
Migration: create processed_webhooks table for Stripe event idempotency.

Prevents duplicate processing when Stripe retries webhook deliveries.
Uses INSERT ... ON CONFLICT DO NOTHING RETURNING as a dedup gate.

Idempotent -- safe to re-run.
"""
import logging
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def migrate():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_webhooks (
            event_id      TEXT PRIMARY KEY,
            event_type    TEXT NOT NULL,
            processed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_processed_webhooks_processed_at
            ON processed_webhooks (processed_at);
    """)
    conn.commit()
    cur.close()
    conn.close()
    log.info("[Migration] processed_webhooks table ready")


if __name__ == "__main__":
    migrate()
