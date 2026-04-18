"""
Migration: add video_kind column to videos for library UI filtering.

Values:
  'short_clip'      — brief single-scene clip (hook, visual, vocab intro)
  'explainer_video' — multi-scene narrated video (concept walkthrough)
  NULL              — unclassified / legacy (treated as explainer_video in UI)

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
        DO $$ BEGIN
            ALTER TABLE videos ADD COLUMN video_kind TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_kind
            ON videos (video_kind)
            WHERE video_kind IS NOT NULL;
    """)
    # Backfill sensible defaults for existing rows: clips under 90s are short clips,
    # everything else is explainer-style. Only fills NULL rows (merge-safe).
    cur.execute("""
        UPDATE videos SET video_kind = 'short_clip'
         WHERE video_kind IS NULL
           AND duration_seconds IS NOT NULL
           AND duration_seconds <= 90;
    """)
    cur.execute("""
        UPDATE videos SET video_kind = 'explainer_video'
         WHERE video_kind IS NULL
           AND duration_seconds IS NOT NULL
           AND duration_seconds > 90;
    """)
    conn.commit()
    cur.close()
    conn.close()
    log.info("[Migration] videos.video_kind column ready")


if __name__ == "__main__":
    migrate()
