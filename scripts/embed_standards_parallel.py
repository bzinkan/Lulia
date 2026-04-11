"""
Parallel standards embedder via Bedrock Titan v2.

The default `align_standards.py embed-standards` calls embed_text() one at a
time inside embed_batch(). At ~7 standards/sec sequential, embedding 1.2M
state standards would take ~47 hours — unacceptable.

This script uses concurrent.futures.ThreadPoolExecutor to make embed_text
calls in parallel (Bedrock Titan v2's default account quota is ~2000 RPM,
so 16 workers ≈ 480 RPM is well within limits).

It pulls a large batch from the DB, embeds the texts in parallel, then
batch-updates the rows. Repeats until no unembedded standards remain.

Idempotent: only touches rows where `embedding IS NULL`. Multiple instances
can run concurrently — the worst-case race is two workers embedding the same
row, the second UPDATE just overwrites with the same vector (slight waste,
final state is correct).

Usage:
    docker compose exec -d api python scripts/embed_standards_parallel.py
    docker compose exec -d api python scripts/embed_standards_parallel.py --workers 32
    docker compose exec -d api python scripts/embed_standards_parallel.py --batch 200
"""
import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Allow running inside the api container
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lms_agents.tools.bedrock_embedding import embed_text  # noqa: E402
from src.lms_agents.tools.db import get_connection  # noqa: E402
from src.lms_agents.tools.standards_alignment import ensure_standards_schema  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
log = logging.getLogger("embed_parallel")


def build_text(row) -> str:
    """Match the exact format used by standards_alignment.embed_all_standards."""
    sid, code, desc, grade, subj, domain = row
    return f"{code}: {desc} (Grade {grade}, {subj}, {domain})"


def fetch_batch(batch_size: int) -> list[tuple]:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT standard_id, code, description, grade_level, subject, domain
               FROM standards
               WHERE embedding IS NULL
               LIMIT %s""",
            (batch_size,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def write_embeddings(updates: list[tuple[str, list[float]]]) -> int:
    """Bulk-write embeddings via prepared UPDATE statements."""
    if not updates:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    written = 0
    try:
        for sid, emb in updates:
            embedding_str = f"[{','.join(str(x) for x in emb)}]"
            cur.execute(
                "UPDATE standards SET embedding = %s::vector WHERE standard_id = %s",
                (embedding_str, sid),
            )
            written += cur.rowcount
        conn.commit()
        return written
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def remaining_count() -> int:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM standards WHERE embedding IS NULL")
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16, help="Parallel embed workers")
    ap.add_argument("--batch", type=int, default=200, help="Rows per fetch/commit")
    args = ap.parse_args()

    ensure_standards_schema()

    initial_remaining = remaining_count()
    log.info(f"Standards to embed: {initial_remaining}")
    log.info(f"Workers: {args.workers}, Batch: {args.batch}")

    if initial_remaining == 0:
        return

    total_done = 0
    total_failed = 0
    started_at = time.time()

    while True:
        rows = fetch_batch(args.batch)
        if not rows:
            break

        # Build (standard_id, text) pairs
        items = [(row[0], build_text(row)) for row in rows]

        # Embed in parallel
        results: list[tuple[str, list[float]]] = []
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            future_to_sid = {
                ex.submit(embed_text, text): sid for sid, text in items
            }
            for fut in as_completed(future_to_sid):
                sid = future_to_sid[fut]
                try:
                    emb = fut.result()
                    if emb is not None:
                        results.append((sid, emb))
                    else:
                        total_failed += 1
                except Exception as e:
                    total_failed += 1
                    log.warning(f"Embed failed for {sid}: {e}")

        # Bulk write
        wrote = write_embeddings(results)
        total_done += wrote

        elapsed = time.time() - started_at
        rate = total_done / elapsed if elapsed > 0 else 0
        eta_sec = (initial_remaining - total_done) / rate if rate > 0 else 0
        eta_min = eta_sec / 60

        log.info(
            f"  Embedded {total_done}/{initial_remaining} "
            f"({total_failed} failed) — {rate:.0f}/sec, ETA {eta_min:.0f} min"
        )

    log.info("=" * 60)
    log.info(f"Done. Embedded {total_done} standards. Failed: {total_failed}")
    log.info(f"Final remaining: {remaining_count()}")


if __name__ == "__main__":
    main()
