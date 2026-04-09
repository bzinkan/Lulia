"""
Migration — add reference_metadata JSONB column to knowledge_chunks.

Enables reference-grounded generation: the Pedagogy Director retrieves
chunks by structural shape (artifact type, visual density, scaffolding)
in addition to semantic similarity, so experts can match real reference
worksheets, slide decks, lesson plans, etc. from the teacher_archive and
teacher_reference lanes.

Run:
    docker compose exec api python scripts/migrate_reference_metadata.py

Non-destructive: column allows NULL, existing rows unaffected. Also
creates a GIN index on the JSONB column for fast attribute queries.
"""
import sys

sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection


MIGRATION_SQL = """
-- Add reference_metadata JSONB column (nullable)
ALTER TABLE knowledge_chunks
    ADD COLUMN IF NOT EXISTS reference_metadata JSONB;

-- GIN index for fast attribute lookups (artifact_type, structural_features, etc.)
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_reference_metadata
    ON knowledge_chunks USING GIN (reference_metadata);

-- Partial index for chunks with analyzed metadata (speeds up exemplar retrieval)
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_reference_analyzed
    ON knowledge_chunks (source_id)
    WHERE reference_metadata IS NOT NULL;
"""


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        print("Running reference_metadata migration...")
        cur.execute(MIGRATION_SQL)
        conn.commit()
        print("  [OK] knowledge_chunks.reference_metadata column added")
        print("  [OK] GIN index on reference_metadata")
        print("  [OK] partial index on analyzed chunks")

        # Verify column exists
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'knowledge_chunks'
              AND column_name = 'reference_metadata'
            """
        )
        row = cur.fetchone()
        if row:
            print(f"  [VERIFIED] {row[0]} ({row[1]})")
        else:
            print("  [ERROR] column not found after migration")
            sys.exit(1)

        # Report current state
        cur.execute(
            "SELECT COUNT(*), COUNT(reference_metadata) FROM knowledge_chunks"
        )
        total, analyzed = cur.fetchone()
        print(
            f"\n  Current state: {total:,} total chunks, "
            f"{analyzed:,} with reference_metadata ({analyzed/total*100:.1f}% coverage)"
        )
    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] migration failed: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
