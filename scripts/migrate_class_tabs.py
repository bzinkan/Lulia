"""
Class Tabs migration — adds columns needed for per-class AI context isolation.

Run with: docker compose exec api python scripts/migrate_class_tabs.py

Idempotent — safe to run multiple times.
"""
import sys
sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection


def migrate():
    conn = get_connection()
    cur = conn.cursor()

    statements = [
        # New columns on classes
        "ALTER TABLE classes ADD COLUMN IF NOT EXISTS template_prefs JSONB DEFAULT '{}'",
        "ALTER TABLE classes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE classes ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP",

        # class_id FK on tables that need it
        "ALTER TABLE knowledge_sources ADD COLUMN IF NOT EXISTS class_id UUID REFERENCES classes(class_id)",
        "ALTER TABLE knowledge_sources ADD COLUMN IF NOT EXISTS scope VARCHAR(10) DEFAULT 'class' CHECK (scope IN ('class', 'teacher'))",
        "ALTER TABLE custom_templates ADD COLUMN IF NOT EXISTS class_id UUID REFERENCES classes(class_id)",
        "ALTER TABLE videos ADD COLUMN IF NOT EXISTS class_id UUID REFERENCES classes(class_id)",

        # Indexes for common queries
        "CREATE INDEX IF NOT EXISTS idx_knowledge_sources_class_id ON knowledge_sources(class_id)",
        "CREATE INDEX IF NOT EXISTS idx_custom_templates_class_id ON custom_templates(class_id)",
        "CREATE INDEX IF NOT EXISTS idx_videos_class_id ON videos(class_id)",
        "CREATE INDEX IF NOT EXISTS idx_classes_teacher_id ON classes(teacher_id)",
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
