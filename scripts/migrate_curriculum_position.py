"""
Migration — Flexible curriculum position tracking.

Extends curriculum_calendar with unit_status, sort_order, generation_source.
Extends class_intelligence with current_calendar_id, position_source, has_curriculum.
Creates standard_activity_log for always-on standards tracking.

Run:
    docker compose exec api python scripts/migrate_curriculum_position.py
"""
import sys

sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection


MIGRATION_SQL = """
-- ================================================================
-- 1. Extend curriculum_calendar with flexible position tracking
-- ================================================================
ALTER TABLE curriculum_calendar
  ADD COLUMN IF NOT EXISTS unit_status VARCHAR(20) DEFAULT 'planned';
  -- 'planned' | 'in_progress' | 'completed' | 'skipped'

ALTER TABLE curriculum_calendar
  ADD COLUMN IF NOT EXISTS sort_order INTEGER;

ALTER TABLE curriculum_calendar
  ADD COLUMN IF NOT EXISTS generation_source VARCHAR(20) DEFAULT 'uploaded';
  -- 'uploaded' | 'ai_generated' | 'manual'

-- Backfill sort_order from week_number for existing rows
UPDATE curriculum_calendar SET sort_order = week_number WHERE sort_order IS NULL;

-- ================================================================
-- 2. Extend class_intelligence with curriculum position pointer
-- ================================================================
ALTER TABLE class_intelligence
  ADD COLUMN IF NOT EXISTS current_calendar_id UUID;

ALTER TABLE class_intelligence
  ADD COLUMN IF NOT EXISTS position_source VARCHAR(20) DEFAULT 'auto';

ALTER TABLE class_intelligence
  ADD COLUMN IF NOT EXISTS has_curriculum BOOLEAN DEFAULT false;

-- ================================================================
-- 3. Create standard_activity_log (always-on tracking)
-- ================================================================
CREATE TABLE IF NOT EXISTS standard_activity_log (
  log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  class_id UUID NOT NULL,
  teacher_id UUID NOT NULL,
  standard_code VARCHAR NOT NULL,
  activity_type VARCHAR NOT NULL,
  source_id VARCHAR,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sal_class ON standard_activity_log(class_id);
CREATE INDEX IF NOT EXISTS idx_sal_teacher ON standard_activity_log(teacher_id);
CREATE INDEX IF NOT EXISTS idx_sal_standard ON standard_activity_log(standard_code);
CREATE INDEX IF NOT EXISTS idx_sal_class_standard ON standard_activity_log(class_id, standard_code);

-- ================================================================
-- 4. Mark existing classes that have curriculum_calendar entries
-- ================================================================
UPDATE class_intelligence ci
SET has_curriculum = true
WHERE EXISTS (
    SELECT 1 FROM curriculum_calendar cc
    WHERE cc.class_id = ci.class_id
);
"""


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        print("Running curriculum position migration...")

        # Execute each statement separately (some ALTERs may already exist)
        for statement in MIGRATION_SQL.split(";"):
            stmt = statement.strip()
            if not stmt or stmt.startswith("--"):
                continue
            try:
                cur.execute(stmt + ";")
                conn.commit()
            except Exception as e:
                conn.rollback()
                # Column already exists is fine
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    pass
                else:
                    print(f"  [WARN] Statement failed: {str(e)[:100]}")

        # Verify
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'curriculum_calendar'
            AND column_name IN ('unit_status', 'sort_order', 'generation_source')
        """)
        cc_cols = [r[0] for r in cur.fetchall()]
        print(f"  [OK] curriculum_calendar new columns: {cc_cols}")

        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'class_intelligence'
            AND column_name IN ('current_calendar_id', 'position_source', 'has_curriculum')
        """)
        ci_cols = [r[0] for r in cur.fetchall()]
        print(f"  [OK] class_intelligence new columns: {ci_cols}")

        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'standard_activity_log'
            )
        """)
        sal_exists = cur.fetchone()[0]
        print(f"  [OK] standard_activity_log table exists: {sal_exists}")

        # Count existing curriculum entries
        cur.execute("SELECT COUNT(*) FROM curriculum_calendar")
        cc_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM class_intelligence WHERE has_curriculum = true")
        ci_with_curr = cur.fetchone()[0]
        print(f"\n  Existing curriculum entries: {cc_count}")
        print(f"  Classes with curriculum: {ci_with_curr}")
        print("\n  Migration complete.")

    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] Migration failed: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
