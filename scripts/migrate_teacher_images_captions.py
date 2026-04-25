"""Add `description` column + tag GIN index to teacher_images.

Supports:
  - Vision-caption lookups at generation time so artifact-mode activities can
    embed the teacher's uploaded images when they're topically relevant.
  - Fast tag-overlap queries via GIN index on the existing `tags` array.

Idempotent — safe to run on an already-migrated database.
"""
import os
import psycopg2


def main():
    url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute(
        """
        ALTER TABLE teacher_images
          ADD COLUMN IF NOT EXISTS description TEXT,
          ADD COLUMN IF NOT EXISTS caption_generated_at TIMESTAMPTZ;

        CREATE INDEX IF NOT EXISTS idx_teacher_images_tags_gin
          ON teacher_images USING GIN (tags);

        CREATE INDEX IF NOT EXISTS idx_teacher_images_description_trgm
          ON teacher_images USING GIN (description gin_trgm_ops);
        """
    )
    # The trigram index needs pg_trgm — enable if not already
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    except Exception:
        pass
    conn.commit()
    cur.close()
    conn.close()
    print("teacher_images: description + indexes ready")


if __name__ == "__main__":
    main()
