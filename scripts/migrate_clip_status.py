"""
Migration: add status column to short_clips and make media fields nullable.

Allows inserting a placeholder row with status='generating' before Veo
completes, so the frontend can poll for progress.

Idempotent -- safe to re-run.
"""
import logging
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def migrate():
    conn = get_connection()
    cur = conn.cursor()
    # Add status column
    cur.execute("""
        DO $$ BEGIN
            ALTER TABLE short_clips ADD COLUMN status TEXT NOT NULL DEFAULT 'complete';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    # Make media fields nullable (they're empty during generation)
    cur.execute("ALTER TABLE short_clips ALTER COLUMN video_uris DROP NOT NULL")
    cur.execute("ALTER TABLE short_clips ALTER COLUMN primary_uri DROP NOT NULL")
    conn.commit()
    cur.close()
    conn.close()
    log.info("[Migration] short_clips.status column + nullable media fields ready")


if __name__ == "__main__":
    migrate()
