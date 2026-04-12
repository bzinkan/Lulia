"""
Backfill `standards.domain` for rows where it's NULL.

Why this script exists
----------------------
The Common Standards Project API returns standards in a tree (depth 0-6).
`scripts/import_standards.py` only sets `domain` on depth-0 nodes ("Physical
Science", "Life Science", etc.) but never inherits that value down to the
actual teachable child standards. Result: 93% of the 1.21M imported standards
have `domain = NULL`, which breaks `StandardsPickerModal` grouping.

What this script does
---------------------
Runs ONE recursive CTE that walks the `standards.parent_id` tree and propagates
the nearest ancestor's `domain` downward. Merge-safe: existing non-NULL
`domain` values are preserved, never overwritten.

Scope invariants (verified):
  - Only modifies `standards.domain`. No other column, no other table.
  - `knowledge_chunks.reference_metadata` is NEVER referenced or touched
    (different table, owned by the reference-grounding pipeline).

Usage:
    docker compose exec api python scripts/backfill_standards_domain.py --dry-run
    docker compose exec api python scripts/backfill_standards_domain.py
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lms_agents.tools.db import get_connection  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
log = logging.getLogger("backfill_domain")


# One iteration propagates domain down ONE level of the tree.
# We loop this until no more rows are updated. This avoids the recursive CTE's
# massive UPDATE-all-at-once which was disk-bound on 1.1M rows and didn't
# finish in 47 minutes. Each level-at-a-time UPDATE is a simple join and
# commits in 5-30 seconds per pass. Tree max depth is 6, so at most 6 passes.
LEVEL_UPDATE_SQL = """
UPDATE standards s
SET domain = p.domain
FROM standards p
WHERE s.parent_id = p.standard_id
  AND p.domain IS NOT NULL AND p.domain != ''
  AND (s.domain IS NULL OR s.domain = '');
"""

# Dry-run: count rows that level 1 would update from the current state.
# (This understates the final total because later levels depend on this level's
# output, but it confirms the query is correct without touching anything.)
DRY_RUN_SQL = """
SELECT COUNT(*)
FROM standards s
JOIN standards p ON s.parent_id = p.standard_id
WHERE p.domain IS NOT NULL AND p.domain != ''
  AND (s.domain IS NULL OR s.domain = '');
"""


def count_status():
    """Return (has_domain, no_domain, total)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
              COUNT(*) FILTER (WHERE domain IS NOT NULL AND domain != '') AS has_domain,
              COUNT(*) FILTER (WHERE domain IS NULL OR domain = '') AS no_domain,
              COUNT(*) AS total
            FROM standards;
        """)
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def dry_run_count():
    """Return how many rows the backfill would update without doing it."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(DRY_RUN_SQL)
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def run_backfill(max_iterations: int = 10) -> int:
    """Execute the backfill one level at a time until no more rows update.

    Returns total rows updated across all iterations.
    Each iteration is its own transaction (commits after each level) so
    progress is preserved if interrupted mid-run.
    """
    conn = get_connection()
    conn.autocommit = True  # each UPDATE is its own transaction — no giant txn
    cur = conn.cursor()
    total = 0
    try:
        for level in range(1, max_iterations + 1):
            log.info(f"  Level {level}: propagating domain down one level...")
            cur.execute(LEVEL_UPDATE_SQL)
            updated = cur.rowcount
            log.info(f"  Level {level}: updated {updated:,} rows")
            total += updated
            if updated == 0:
                log.info(f"  Converged at level {level} — no more rows to update.")
                break
        else:
            log.warning(
                f"Hit max_iterations={max_iterations} without converging. "
                "Tree may be deeper than expected; re-run to continue."
            )
        return total
    finally:
        cur.close()
        conn.close()


def main():
    ap = argparse.ArgumentParser(
        description="Backfill standards.domain via recursive CTE (merge-safe).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows that would be updated without committing.",
    )
    args = ap.parse_args()

    has_before, none_before, total = count_status()
    log.info(f"Before backfill:")
    log.info(f"  has_domain: {has_before:,}")
    log.info(f"  no_domain:  {none_before:,}")
    log.info(f"  total:      {total:,}")

    if none_before == 0:
        log.info("Nothing to do — every standard already has a domain.")
        return

    if args.dry_run:
        log.info("DRY RUN — checking how many rows level 1 would update...")
        would = dry_run_count()
        log.info(
            f"Level 1 would update: {would:,} rows. "
            "(Later levels cascade from this; total will be ~{none_before:,} minus orphan subtrees.)"
        )
        return

    log.info("Running level-by-level backfill...")
    updated = run_backfill()
    log.info(f"Total rows updated: {updated:,}")

    has_after, none_after, _ = count_status()
    log.info(f"After backfill:")
    log.info(f"  has_domain: {has_after:,}  (+{has_after - has_before:,})")
    log.info(f"  no_domain:  {none_after:,}  ({none_before - none_after:,} fewer)")

    if none_after > 0:
        log.info(
            f"{none_after:,} standards still have NULL domain — "
            "these are orphan subtrees (no domain-bearing ancestor). "
            "Consider Step 2 (Haiku classifier) if these surface in the picker."
        )


if __name__ == "__main__":
    main()
