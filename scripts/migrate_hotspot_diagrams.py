"""
Migration: create hotspot_diagrams table for AI-generated labeled diagrams
with vision-extracted hotspot coordinates.

Each row is a unique (subject + sorted parts) combo so identical requests
across teachers reuse the same generated image. Hot caching matters here
since each diagram costs ~$0.005 (Leonardo) + ~$0.005 (Claude vision).

Idempotent — safe to re-run.
"""
import logging
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def migrate():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hotspot_diagrams (
            cache_key      TEXT PRIMARY KEY,
            subject        TEXT NOT NULL,
            parts_json     JSONB NOT NULL,
            image_url      TEXT NOT NULL,
            image_width    INT NOT NULL DEFAULT 1024,
            image_height   INT NOT NULL DEFAULT 1024,
            hotspots_json  JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_hotspot_diagrams_subject
            ON hotspot_diagrams (subject)
    """)
    conn.commit()
    cur.close()
    conn.close()
    log.info("[Migration] hotspot_diagrams table ready")


if __name__ == "__main__":
    migrate()
