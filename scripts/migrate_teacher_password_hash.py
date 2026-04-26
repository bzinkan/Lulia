"""Add password_hash column to teachers (Phase 28 auth)."""
from src.lms_agents.tools.db import get_connection


def main():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """ALTER TABLE teachers
             ADD COLUMN IF NOT EXISTS password_hash TEXT;
           CREATE INDEX IF NOT EXISTS idx_teachers_email_lower
             ON teachers (LOWER(email));"""
    )
    conn.commit()
    cur.close()
    conn.close()
    print("teachers: password_hash column ready, idx_teachers_email_lower built")


if __name__ == "__main__":
    main()
