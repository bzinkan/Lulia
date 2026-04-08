"""
Class Intelligence migration — creates the class_intelligence table for
per-class AI context accumulation.

Run with: docker compose exec api python scripts/migrate_class_intelligence.py

Idempotent — safe to run multiple times.
"""
import sys
sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection


def migrate():
    conn = get_connection()
    cur = conn.cursor()

    statements = [
        """CREATE TABLE IF NOT EXISTS class_intelligence (
            class_id UUID PRIMARY KEY REFERENCES classes(class_id),

            -- Standards coverage tracking
            standards_covered JSONB DEFAULT '[]',
            standards_in_progress JSONB DEFAULT '[]',

            -- Vocabulary/concepts introduced
            vocabulary_introduced JSONB DEFAULT '[]',
            key_concepts JSONB DEFAULT '[]',

            -- Activity effectiveness tracking
            activity_ratings JSONB DEFAULT '[]',
            preferred_activity_types JSONB DEFAULT '[]',

            -- Student group insights
            common_misconceptions JSONB DEFAULT '[]',
            class_strengths JSONB DEFAULT '[]',
            class_challenges JSONB DEFAULT '[]',

            -- Pacing
            pacing_status VARCHAR(20) DEFAULT 'on_track',
            pacing_notes TEXT DEFAULT '',
            units_completed JSONB DEFAULT '[]',
            current_unit TEXT DEFAULT '',

            -- AI context summary (rebuilt periodically)
            ai_context_summary TEXT DEFAULT '',

            -- Timestamps
            last_updated TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]

    for stmt in statements:
        try:
            cur.execute(stmt)
            conn.commit()
            print(f"OK: {stmt[:70]}...")
        except Exception as e:
            print(f"SKIP: {stmt[:70]}... ({e})")
            conn.rollback()

    cur.close()
    conn.close()
    print("Migration complete")


if __name__ == "__main__":
    migrate()
