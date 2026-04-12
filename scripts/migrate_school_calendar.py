"""
Migration — create school_calendar table for tracking school days, holidays, PD days.

Run:
    docker compose exec api python scripts/migrate_school_calendar.py
"""
import sys
sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection

def main():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS school_calendar (
                calendar_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                teacher_id UUID NOT NULL,
                school_year VARCHAR NOT NULL,
                date DATE NOT NULL,
                day_type VARCHAR NOT NULL DEFAULT 'school_day',
                label VARCHAR,
                notes TEXT,
                UNIQUE(teacher_id, date)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_school_cal_teacher_date
            ON school_calendar(teacher_id, date)
        """)
        conn.commit()
        print("[OK] school_calendar table created")

        cur.execute("SELECT COUNT(*) FROM school_calendar")
        print(f"[OK] {cur.fetchone()[0]} rows")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
