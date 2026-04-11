"""
Offline chunk-to-standards alignment via provider-agnostic dispatch.

Why offline?
------------
The built-in synchronous alignment path (`scripts/align_standards.py align-all`)
calls Anthropic Haiku one chunk at a time. At 52K chunks that's ~$180 and ~5
hours. This offline script writes all the judgment prompts to a JSONL file and
submits them via OpenAI's Batch API (50% off, 24-hour SLA, atomic) for ~$20.

The merge-safe writeback is the key feature: `grade_bands` is UNIONed with
any existing folder-based values instead of overwritten, so the manual
backfill this session (8,372 chunks → 6-8, etc.) is preserved.

Usage
-----
Prepare (local, free):
    python scripts/align_standards_offline.py prepare --full-kb
    python scripts/align_standards_offline.py prepare --teacher-only
    python scripts/align_standards_offline.py prepare --source-id <uuid>
    python scripts/align_standards_offline.py prepare --limit 100   # smoke test

Submit to OpenAI Batch API:
    python scripts/align_standards_offline.py submit
    # prints a batch_id; save it

Poll batch status:
    python scripts/align_standards_offline.py poll <batch_id>

Writeback results to DB (merge-safe):
    python scripts/align_standards_offline.py writeback <batch_id>

Direct synchronous run (bypass batch, use any provider):
    ALIGN_PROVIDER=groq python scripts/align_standards_offline.py run-sync --limit 100
    ALIGN_PROVIDER=openai-sync python scripts/align_standards_offline.py run-sync --full-kb
    ALIGN_PROVIDER=anthropic-sync python scripts/align_standards_offline.py run-sync --teacher-only
    ALIGN_PROVIDER=ollama python scripts/align_standards_offline.py run-sync --limit 20

Output artifacts
----------------
  scripts/align_batch_input.jsonl   — Prompts in OpenAI Batch API format
  scripts/align_batch_meta.json     — Map from custom_id → chunk_id (writeback needs this)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Allow running inside the api container
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from psycopg2.extras import Json  # noqa: E402

from src.lms_agents.tools.alignment_providers import (  # noqa: E402
    build_alignment_prompt,
    get_provider,
    list_providers,
    parse_response,
)
from src.lms_agents.tools.db import get_connection  # noqa: E402
from src.lms_agents.tools.standards_alignment import ensure_standards_schema  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
log = logging.getLogger("align_offline")

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSONL = SCRIPT_DIR / "align_batch_input.jsonl"
DEFAULT_META = SCRIPT_DIR / "align_batch_meta.json"
DEFAULT_RESULTS = SCRIPT_DIR / "align_batch_output.jsonl"


# ---------------------------------------------------------------------------
# Chunk fetching
# ---------------------------------------------------------------------------

def fetch_unaligned_chunks(
    scope: str = "full",
    source_id: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Fetch chunks that need alignment.

    scope:
      "full"         — every unaligned chunk in the KB
      "teacher"      — teacher_archive + teacher_reference lanes only
      "source"       — one specific source_id (ignores `scope` if source_id set)
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT kc.chunk_id, kc.content, kc.embedding, ks.subject, ks.grade_level,
                   kc.grade_bands
            FROM knowledge_chunks kc
            JOIN knowledge_sources ks ON kc.source_id = ks.source_id
            WHERE (kc.alignment_scores = '[]'::jsonb OR kc.alignment_scores IS NULL)
              AND kc.embedding IS NOT NULL
        """
        params: list = []

        if source_id:
            query += " AND kc.source_id = %s::uuid"
            params.append(source_id)
        elif scope == "teacher":
            query += " AND ks.upload_lane IN ('teacher_archive', 'teacher_reference')"

        query += " ORDER BY kc.chunk_id"
        if limit:
            query += " LIMIT %s"
            params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        cur.close()
        conn.close()


def fetch_candidate_standards(chunk_embedding, subject: str | None, top_k: int = 20) -> list[dict]:
    """pgvector top-K retrieval for candidate standards, optionally subject-filtered."""
    if chunk_embedding is None:
        return []

    if isinstance(chunk_embedding, str):
        embedding_str = chunk_embedding
    else:
        try:
            embedding_list = list(chunk_embedding)
        except Exception:
            return []
        embedding_str = f"[{','.join(str(x) for x in embedding_list)}]"

    conn = get_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT s.standard_id, s.code, s.description, s.grade_level, s.subject,
                   s.domain
            FROM standards s
            JOIN standards_frameworks f ON s.framework_id = f.framework_id
            WHERE f.is_active = true
              AND s.embedding IS NOT NULL
        """
        params: list = []
        # Subject filter REMOVED. State standards use inconsistent subject labels
        # (e.g., "Math" vs "Mathematics", "ELA" vs "English Language Arts") and
        # filtering causes entire subjects to return zero candidates. With the
        # HNSW index on standards.embedding, a full-pool search is ~1ms per chunk
        # and embedding distance is a better discriminator than text matching.
        # See: the Mathematics/Physics/Biology/Chemistry/ELA zero-alignment bug
        # discovered during the Anthropic Haiku run on 2026-04-10.

        query += " ORDER BY s.embedding <=> %s::vector ASC LIMIT %s"
        params.extend([embedding_str, top_k])

        cur.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Prepare — write JSONL for OpenAI Batch API
# ---------------------------------------------------------------------------

def cmd_prepare(args) -> None:
    ensure_standards_schema()

    if args.source_id:
        chunks = fetch_unaligned_chunks(source_id=args.source_id, limit=args.limit)
    elif args.teacher_only:
        chunks = fetch_unaligned_chunks(scope="teacher", limit=args.limit)
    else:
        chunks = fetch_unaligned_chunks(scope="full", limit=args.limit)

    if not chunks:
        log.info("No unaligned chunks found. Nothing to prepare.")
        return

    log.info(f"Preparing batch input for {len(chunks)} chunks...")

    jsonl_path = Path(args.output) if args.output else DEFAULT_JSONL
    meta_path = Path(args.meta) if args.meta else DEFAULT_META
    model = os.environ.get("OPENAI_ALIGN_MODEL", "gpt-4o-mini")

    meta: dict[str, str] = {}
    written = 0
    skipped_no_candidates = 0

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            candidates = fetch_candidate_standards(
                chunk["embedding"], subject=chunk.get("subject"), top_k=20
            )
            if not candidates:
                skipped_no_candidates += 1
                continue

            prompt = build_alignment_prompt(chunk["content"], candidates)
            custom_id = f"chunk-{i:06d}"
            meta[custom_id] = str(chunk["chunk_id"])

            request_obj = {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            }
            f.write(json.dumps(request_obj) + "\n")
            written += 1

            if written % 500 == 0:
                log.info(f"  Prepared {written}/{len(chunks)}")

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)

    log.info("=" * 60)
    log.info(f"Wrote {written} prompts to {jsonl_path}")
    log.info(f"Wrote meta map to {meta_path}")
    log.info(f"Skipped (no candidate standards): {skipped_no_candidates}")
    log.info(f"Model: {model}")
    if written > 0:
        est_cost = written * 0.00038
        log.info(f"Estimated OpenAI Batch API cost: ~${est_cost:.2f}")


# ---------------------------------------------------------------------------
# Submit — upload JSONL to OpenAI Batch API
# ---------------------------------------------------------------------------

def cmd_submit(args) -> None:
    jsonl_path = Path(args.input) if args.input else DEFAULT_JSONL
    if not jsonl_path.exists():
        log.error(f"Input file not found: {jsonl_path}. Run 'prepare' first.")
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.error("OPENAI_API_KEY not set")
        sys.exit(1)

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    log.info(f"Uploading {jsonl_path}...")
    with open(jsonl_path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")
    log.info(f"  file_id={file_obj.id}")

    log.info("Creating batch job...")
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"source": "lulia-align-standards-offline"},
    )

    log.info("=" * 60)
    log.info(f"Batch ID: {batch.id}")
    log.info(f"Status:   {batch.status}")
    log.info(f"Poll with: python scripts/align_standards_offline.py poll {batch.id}")


# ---------------------------------------------------------------------------
# Poll — check batch status
# ---------------------------------------------------------------------------

def cmd_poll(args) -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.error("OPENAI_API_KEY not set")
        sys.exit(1)

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    batch = client.batches.retrieve(args.batch_id)
    log.info(f"Batch {batch.id}")
    log.info(f"  Status:           {batch.status}")
    log.info(f"  Created at:       {batch.created_at}")
    log.info(f"  Completed count:  {batch.request_counts.completed}/{batch.request_counts.total}")
    log.info(f"  Failed count:     {batch.request_counts.failed}")
    if batch.status == "completed":
        log.info(f"  Output file:      {batch.output_file_id}")
        log.info(f"  Download with: python scripts/align_standards_offline.py writeback {batch.id}")


# ---------------------------------------------------------------------------
# Writeback — download results and apply to DB with merge-safe grade_bands
# ---------------------------------------------------------------------------

def _apply_result_to_db(cur, chunk_id: str, parsed: dict) -> bool:
    """
    Apply one alignment result to the DB.

    CRITICAL: `grade_bands` is MERGED (union), never overwritten.
    The other three target columns (alignment_scores, reading_level,
    standards_tags) start empty and are cleanly overwritten.
    """
    alignments = parsed.get("alignments", [])
    reading_level = parsed.get("reading_level")
    new_grade_bands = parsed.get("grade_bands") or []

    # Look up standard_id + framework_tier for each aligned code
    alignment_scores: list[dict] = []
    standards_tags: list[str] = []
    for a in alignments:
        code = a.get("code")
        strength = a.get("strength", "partial")
        if not code:
            continue
        cur.execute(
            """SELECT s.standard_id, f.tier
               FROM standards s
               JOIN standards_frameworks f ON s.framework_id = f.framework_id
               WHERE s.code = %s AND f.is_active = true
               LIMIT 1""",
            (code,),
        )
        row = cur.fetchone()
        if row:
            sid, tier = row
            alignment_scores.append({
                "standard_id": str(sid),
                "code": code,
                "strength": strength,
                "framework_tier": tier,
            })
            standards_tags.append(code)

    # Merge-safe update:
    #   - grade_bands:    UNION (folder tags + LLM tags; see feedback-authoritative-data.md)
    #   - standards_tags: UNION (reference-grounding pipeline may have pre-populated this)
    #   - alignment_scores: clean overwrite (this column is exclusively ours; plan invariant)
    #   - reading_level:    clean overwrite (was NULL; if non-NULL from another pipeline,
    #                       the newer LLM estimate replaces it — document if this changes)
    #   - reference_metadata: NEVER touched. This column is owned by the reference-grounding
    #                         agent. Not named in this UPDATE. Verified via md5 dry-run.
    cur.execute(
        """UPDATE knowledge_chunks
           SET alignment_scores = %s,
               reading_level    = %s,
               standards_tags   = (
                   SELECT COALESCE(jsonb_agg(DISTINCT tag), '[]'::jsonb)
                   FROM jsonb_array_elements_text(
                       COALESCE(standards_tags, '[]'::jsonb) || %s::jsonb
                   ) AS tag
               ),
               grade_bands      = ARRAY(
                   SELECT DISTINCT unnest(
                       COALESCE(grade_bands, '{}'::text[]) || %s::text[]
                   )
               )
           WHERE chunk_id = %s""",
        (
            Json(alignment_scores),
            reading_level,
            Json(standards_tags),
            new_grade_bands,
            chunk_id,
        ),
    )
    return cur.rowcount > 0


def cmd_writeback(args) -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.error("OPENAI_API_KEY not set")
        sys.exit(1)

    meta_path = Path(args.meta) if args.meta else DEFAULT_META
    if not meta_path.exists():
        log.error(f"Meta file not found: {meta_path}. Was 'prepare' run?")
        sys.exit(1)
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    batch = client.batches.retrieve(args.batch_id)
    if batch.status != "completed":
        log.error(f"Batch status={batch.status}, not ready for writeback")
        sys.exit(1)
    if not batch.output_file_id:
        log.error("Batch has no output_file_id")
        sys.exit(1)

    results_path = Path(args.results) if args.results else DEFAULT_RESULTS
    log.info(f"Downloading results to {results_path}...")
    content = client.files.content(batch.output_file_id).read()
    with open(results_path, "wb") as f:
        f.write(content)

    log.info("Applying results to DB (merge-safe)...")
    conn = get_connection()
    cur = conn.cursor()

    applied = 0
    parse_errors = 0
    missing_chunks = 0
    try:
        with open(results_path, encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    parse_errors += 1
                    continue

                custom_id = obj.get("custom_id")
                chunk_id = meta.get(custom_id)
                if not chunk_id:
                    missing_chunks += 1
                    continue

                response = obj.get("response") or {}
                body = response.get("body") or {}
                choices = body.get("choices") or []
                if not choices:
                    parse_errors += 1
                    continue

                text = choices[0].get("message", {}).get("content", "")
                parsed = parse_response(text)
                if parsed is None:
                    parse_errors += 1
                    continue

                if _apply_result_to_db(cur, chunk_id, parsed):
                    applied += 1

                if applied % 500 == 0 and applied > 0:
                    conn.commit()
                    log.info(f"  Applied {applied} so far...")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    log.info("=" * 60)
    log.info(f"Writeback complete")
    log.info(f"  Applied:      {applied}")
    log.info(f"  Parse errors: {parse_errors}")
    log.info(f"  Missing meta: {missing_chunks}")


# ---------------------------------------------------------------------------
# run-sync — bypass batch, align synchronously via any provider
# ---------------------------------------------------------------------------

def _align_one_chunk(chunk: dict, provider) -> tuple[str, dict | None]:
    """Align a single chunk: retrieve candidates → build prompt → call LLM.

    Returns (chunk_id, parsed_result_or_None). Thread-safe — each call uses
    its own DB connection for candidate retrieval.
    """
    candidates = fetch_candidate_standards(
        chunk["embedding"], subject=chunk.get("subject"), top_k=20
    )
    if not candidates:
        return (str(chunk["chunk_id"]), None)
    prompt = build_alignment_prompt(chunk["content"], candidates)
    parsed = provider(prompt)
    return (str(chunk["chunk_id"]), parsed)


def cmd_run_sync(args) -> None:
    ensure_standards_schema()

    provider_name = os.environ.get("ALIGN_PROVIDER", "openai-sync")
    if provider_name == "openai-batch":
        log.error("run-sync does not support openai-batch. Use prepare/submit/poll/writeback.")
        sys.exit(1)

    provider = get_provider(provider_name)
    workers = getattr(args, "workers", 1) or 1
    log.info(f"Provider: {provider_name}, Workers: {workers}")

    if args.source_id:
        chunks = fetch_unaligned_chunks(source_id=args.source_id, limit=args.limit)
    elif args.teacher_only:
        chunks = fetch_unaligned_chunks(scope="teacher", limit=args.limit)
    else:
        chunks = fetch_unaligned_chunks(scope="full", limit=args.limit)

    if not chunks:
        log.info("No unaligned chunks found.")
        return

    log.info(f"Aligning {len(chunks)} chunks via {provider_name} ({workers} workers)...")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    applied = 0
    failed = 0
    total = len(chunks)
    started_at = time.time()

    # Process in mini-batches so we commit and log progress periodically
    COMMIT_EVERY = 50

    conn = get_connection()
    cur = conn.cursor()

    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(_align_one_chunk, chunk, provider): chunk
                for chunk in chunks
            }
            for i, fut in enumerate(as_completed(futures)):
                chunk_id, parsed = fut.result()
                if parsed is None:
                    failed += 1
                else:
                    if _apply_result_to_db(cur, chunk_id, parsed):
                        applied += 1
                    else:
                        failed += 1

                if (i + 1) % COMMIT_EVERY == 0:
                    conn.commit()
                    elapsed = time.time() - started_at
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    eta_min = (total - i - 1) / rate / 60 if rate > 0 else 0
                    log.info(
                        f"  Progress: {i + 1}/{total} "
                        f"(applied={applied} failed={failed}) "
                        f"— {rate:.1f}/sec, ETA {eta_min:.0f} min"
                    )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    elapsed = time.time() - started_at
    log.info("=" * 60)
    log.info(f"Sync alignment complete in {elapsed/60:.0f} min")
    log.info(f"  Applied: {applied}")
    log.info(f"  Failed:  {failed}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Offline chunk-to-standards alignment (provider-agnostic)."
    )
    sub = ap.add_subparsers(dest="command", required=True)

    # prepare
    p = sub.add_parser("prepare", help="Write OpenAI Batch JSONL input")
    scope_group = p.add_mutually_exclusive_group()
    scope_group.add_argument("--full-kb", action="store_true", help="All unaligned chunks (default)")
    scope_group.add_argument("--teacher-only", action="store_true", help="Only teacher_archive + teacher_reference lanes")
    scope_group.add_argument("--source-id", type=str, help="Only chunks from a specific source_id")
    p.add_argument("--limit", type=int, default=None, help="Max chunks (smoke tests)")
    p.add_argument("--output", type=str, default=None, help=f"JSONL output path (default: {DEFAULT_JSONL})")
    p.add_argument("--meta", type=str, default=None, help=f"Meta JSON path (default: {DEFAULT_META})")
    p.set_defaults(func=cmd_prepare)

    # submit
    p = sub.add_parser("submit", help="Upload JSONL to OpenAI Batch API")
    p.add_argument("--input", type=str, default=None, help=f"JSONL input path (default: {DEFAULT_JSONL})")
    p.set_defaults(func=cmd_submit)

    # poll
    p = sub.add_parser("poll", help="Check OpenAI batch status")
    p.add_argument("batch_id", type=str)
    p.set_defaults(func=cmd_poll)

    # writeback
    p = sub.add_parser("writeback", help="Download results and apply to DB (merge-safe)")
    p.add_argument("batch_id", type=str)
    p.add_argument("--meta", type=str, default=None)
    p.add_argument("--results", type=str, default=None)
    p.set_defaults(func=cmd_writeback)

    # run-sync
    p = sub.add_parser("run-sync", help="Align synchronously via $ALIGN_PROVIDER (not batch)")
    scope_group = p.add_mutually_exclusive_group()
    scope_group.add_argument("--full-kb", action="store_true")
    scope_group.add_argument("--teacher-only", action="store_true")
    scope_group.add_argument("--source-id", type=str)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=8, help="Parallel LLM call workers (default: 8)")
    p.set_defaults(func=cmd_run_sync)

    # providers
    p = sub.add_parser("providers", help="List supported providers")
    p.set_defaults(func=lambda a: print("\n".join(list_providers())))

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
