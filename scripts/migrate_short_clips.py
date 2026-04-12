"""
Migration: create short_clips table for Veo 3 Fast generations.

Each row stores the teacher-owned clip plus its Veo segment URIs, the prompt,
and how many credits were charged. Deferred fields (class_id, topic_label)
are optional so the table works from any entry point (Clips tab, Planner, Print & Go).

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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS short_clips (
            clip_id         UUID PRIMARY KEY,
            teacher_id      UUID NOT NULL,
            class_id        UUID,
            prompt          TEXT NOT NULL,
            topic_label     VARCHAR(255),
            duration_sec    INT NOT NULL,
            aspect_ratio    VARCHAR(12) NOT NULL DEFAULT '16:9',
            video_uris      TEXT[] NOT NULL,
            primary_uri     TEXT NOT NULL,
            segments        INT NOT NULL DEFAULT 1,
            model           VARCHAR(64),
            credits_charged INT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_short_clips_teacher ON short_clips(teacher_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_short_clips_class ON short_clips(class_id)")
    conn.commit()
    cur.close()
    conn.close()
    log.info("short_clips table ready.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        log.error(f"Migration failed: {e}")
        sys.exit(1)
