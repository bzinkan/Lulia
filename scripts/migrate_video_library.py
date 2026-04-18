"""
Migration — extend `videos` table for the Video Library feature.

Adds library-specific columns (class_id, grade_level, subject, domain,
grade_bands, reading_level, hosting_type, youtube_video_id, external_url,
source_lane, scope, attribution, license, source_url) plus a video_standards
join table for many-to-many video↔standard alignment.

Non-destructive and idempotent:
  - All ALTER TABLE statements use IF NOT EXISTS
  - CREATE TABLE + CREATE INDEX use IF NOT EXISTS
  - Existing video rows get safe defaults (hosting_type='self_hosted',
    source_lane='generated', scope='teacher') matching pre-migration behavior
  - `reference_metadata` on knowledge_chunks is NEVER touched

Run:
    docker compose exec api python scripts/migrate_video_library.py
"""
import sys

sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection


MIGRATION_SQL = """
-- -------------------------------------------------------------------------
-- videos: library columns
-- -------------------------------------------------------------------------

ALTER TABLE videos ADD COLUMN IF NOT EXISTS class_id UUID REFERENCES classes(class_id);
ALTER TABLE videos ADD COLUMN IF NOT EXISTS grade_level VARCHAR;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS subject VARCHAR;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS domain VARCHAR;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS grade_bands TEXT[] DEFAULT '{}';
ALTER TABLE videos ADD COLUMN IF NOT EXISTS reading_level REAL;

-- hosting_type: where the video actually lives / how the frontend plays it
--   'self_hosted'   — MP4 on our S3 (teacher uploads, Lulia-generated, premium)
--   'youtube_embed' — plays via <iframe>, we store youtube_video_id only
--   'external_url'  — link out or embed external iframe
ALTER TABLE videos ADD COLUMN IF NOT EXISTS hosting_type VARCHAR NOT NULL DEFAULT 'self_hosted';
ALTER TABLE videos ADD COLUMN IF NOT EXISTS youtube_video_id VARCHAR;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS external_url TEXT;

-- source_lane: where the video came from (for filtering + analytics)
--   'generated'         — produced by video_crew.generate_video() on demand
--   'teacher_upload'    — uploaded by a teacher
--   'youtube_embed'     — ingested from a curated YouTube channel
--   'oer_public_domain' — downloaded from NASA / Smithsonian / LoC / etc.
--   'lulia_signature'   — curated premium content (e.g. Flow-generated)
ALTER TABLE videos ADD COLUMN IF NOT EXISTS source_lane VARCHAR NOT NULL DEFAULT 'generated';

-- scope: who can see this video in browse queries
--   'teacher' — uploader only (their own classes)
--   'class'   — all teachers in a specific class_id (rare, future-friendly)
--   'public'  — everyone on the platform
ALTER TABLE videos ADD COLUMN IF NOT EXISTS scope VARCHAR NOT NULL DEFAULT 'teacher';

ALTER TABLE videos ADD COLUMN IF NOT EXISTS attribution TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS license VARCHAR;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS source_url TEXT;

-- -------------------------------------------------------------------------
-- video_standards: many-to-many video ↔ standard join
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS video_standards (
    video_id    UUID    NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    standard_id UUID    NOT NULL REFERENCES standards(standard_id) ON DELETE CASCADE,
    strength    VARCHAR NOT NULL,  -- 'strong' | 'partial'
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (video_id, standard_id)
);

-- -------------------------------------------------------------------------
-- Indexes for library browse queries
-- -------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_videos_class           ON videos(class_id);
CREATE INDEX IF NOT EXISTS idx_videos_scope_lane      ON videos(scope, source_lane);
CREATE INDEX IF NOT EXISTS idx_videos_grade_subject   ON videos(grade_level, subject);
CREATE INDEX IF NOT EXISTS idx_videos_hosting         ON videos(hosting_type);
CREATE INDEX IF NOT EXISTS idx_videos_youtube_id      ON videos(youtube_video_id)
    WHERE youtube_video_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_video_standards_std    ON video_standards(standard_id);
CREATE INDEX IF NOT EXISTS idx_video_standards_strong ON video_standards(video_id, strength)
    WHERE strength = 'strong';
"""


VERIFY_SQL = """
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'videos'
ORDER BY ordinal_position;
"""


REQUIRED_COLUMNS = {
    "class_id", "grade_level", "subject", "domain", "grade_bands", "reading_level",
    "hosting_type", "youtube_video_id", "external_url", "source_lane", "scope",
    "attribution", "license", "source_url",
}


def main() -> None:
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    # --- reference_metadata invariant check (BEFORE) ---
    cur.execute("""
        SELECT COALESCE(md5(string_agg(reference_metadata::text, '' ORDER BY chunk_id)), 'empty')
        FROM knowledge_chunks
        WHERE reference_metadata IS NOT NULL;
    """)
    ref_meta_before = cur.fetchone()[0]
    print(f"reference_metadata checksum BEFORE: {ref_meta_before}")

    # --- Run the migration ---
    try:
        for stmt in MIGRATION_SQL.strip().split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            # Show the first comment/line of each statement
            first_line = next((ln for ln in stmt.split("\n") if ln.strip() and not ln.strip().startswith("--")), stmt)
            print(f"  -> {first_line[:80]}")
            cur.execute(stmt)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Migration FAILED: {e}")
        raise

    # --- Verify required columns landed ---
    cur.execute(VERIFY_SQL)
    actual_columns = {row[0] for row in cur.fetchall()}
    missing = REQUIRED_COLUMNS - actual_columns
    if missing:
        print(f"ERROR: missing columns after migration: {missing}")
        sys.exit(1)
    print(f"All {len(REQUIRED_COLUMNS)} library columns present on videos table.")

    # --- Verify join table ---
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'video_standards';
    """)
    if cur.fetchone()[0] != 1:
        print("ERROR: video_standards table not created")
        sys.exit(1)
    print("video_standards join table present.")

    # --- reference_metadata invariant check (AFTER) ---
    cur.execute("""
        SELECT COALESCE(md5(string_agg(reference_metadata::text, '' ORDER BY chunk_id)), 'empty')
        FROM knowledge_chunks
        WHERE reference_metadata IS NOT NULL;
    """)
    ref_meta_after = cur.fetchone()[0]
    print(f"reference_metadata checksum AFTER:  {ref_meta_after}")
    if ref_meta_before != ref_meta_after:
        print("ERROR: reference_metadata changed during migration — investigate!")
        sys.exit(1)
    print("reference_metadata untouched — invariant held.")

    cur.close()
    conn.close()
    print("\nVideo library migration complete.")


if __name__ == "__main__":
    main()
