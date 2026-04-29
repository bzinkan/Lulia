"""Create the canonical prebuilt activity library table."""
import os
import sys

sys.path.insert(0, os.environ.get("APP_ROOT", "/app"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lms_agents.tools.db import get_connection


MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS prebuilt_activities (
    activity_id TEXT PRIMARY KEY,
    grade_level TEXT,
    grade_band TEXT,
    subject TEXT NOT NULL,
    course TEXT,
    unit_number INT,
    unit_title TEXT,
    lesson_number INT,
    lesson_title TEXT,
    activity_type TEXT NOT NULL,
    standards JSONB DEFAULT '[]'::jsonb,
    visual_surface JSONB DEFAULT '{}'::jsonb,
    content JSONB DEFAULT '{}'::jsonb,
    checks JSONB DEFAULT '[]'::jsonb,
    reflection_prompt JSONB DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    difficulty TEXT DEFAULT 'core',
    estimated_minutes INT DEFAULT 10,
    status TEXT DEFAULT 'draft',
    source TEXT DEFAULT 'lulia_prebuilt',
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prebuilt_activities_grade_subject
ON prebuilt_activities (grade_level, subject);

CREATE INDEX IF NOT EXISTS idx_prebuilt_activities_course
ON prebuilt_activities (course);

CREATE INDEX IF NOT EXISTS idx_prebuilt_activities_unit
ON prebuilt_activities (course, unit_number, lesson_number);

CREATE INDEX IF NOT EXISTS idx_prebuilt_activities_type
ON prebuilt_activities (activity_type);

CREATE INDEX IF NOT EXISTS idx_prebuilt_activities_tags
ON prebuilt_activities USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_prebuilt_activities_standards
ON prebuilt_activities USING GIN (standards);
"""


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(MIGRATION_SQL)
        conn.commit()
        cur.execute("SELECT to_regclass('public.prebuilt_activities')")
        table = cur.fetchone()[0]
        if table != "prebuilt_activities":
            raise RuntimeError("prebuilt_activities table was not created")
        print("[OK] prebuilt_activities table ready")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
