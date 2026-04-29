"""Add description/caption metadata and search indexes to teacher_images."""
import os
import sys

sys.path.insert(0, os.environ.get("APP_ROOT", "/app"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lms_agents.tools.db import get_connection


def main():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
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
        conn.commit()
    finally:
        cur.close()
        conn.close()
    print("teacher_images: description + indexes ready")


if __name__ == "__main__":
    main()
