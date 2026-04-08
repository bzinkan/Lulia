"""
Migration — Add Canva OAuth columns to the teachers table.

Run: python -m scripts.migrate_canva
"""
import os
import sys

import psycopg2

SQL = """
ALTER TABLE teachers ADD COLUMN IF NOT EXISTS canva_access_token TEXT;
ALTER TABLE teachers ADD COLUMN IF NOT EXISTS canva_refresh_token TEXT;
ALTER TABLE teachers ADD COLUMN IF NOT EXISTS canva_token_expires_at TIMESTAMP;
ALTER TABLE teachers ADD COLUMN IF NOT EXISTS canva_code_verifier TEXT;
"""


def main():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )
    cur = conn.cursor()
    for stmt in SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            print(f"  -> {stmt[:60]}...")
            cur.execute(stmt)
    conn.commit()
    cur.close()
    conn.close()
    print("Canva migration complete.")


if __name__ == "__main__":
    main()
