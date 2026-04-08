#!/usr/bin/env python3
"""
CLI for standards alignment operations.

Usage:
    python scripts/align_standards.py embed-standards
    python scripts/align_standards.py align --source-id=<uuid>
    python scripts/align_standards.py align-all
    python scripts/align_standards.py status
    python scripts/align_standards.py test-retrieval --code=5-PS1-1 --grade=5
"""
import argparse
import json
import logging
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from src.lms_agents.tools.standards_alignment import (
    align_all_unaligned,
    align_chunks_batch,
    alignment_status,
    embed_all_standards,
    ensure_standards_schema,
    retrieve_for_standard,
    retrieve_for_teaching_assignment,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


def cmd_embed_standards(args):
    """Embed all 62K+ standards that don't have embeddings yet."""
    log.info("Starting standards embedding...")
    count = embed_all_standards(batch_size=args.batch_size)
    log.info(f"Done. Embedded {count} standards.")


def cmd_align(args):
    """Align chunks from a specific source (or all if no source-id)."""
    log.info(f"Aligning chunks (source_id={args.source_id}, limit={args.limit})...")
    count = align_chunks_batch(source_id=args.source_id, limit=args.limit)
    log.info(f"Done. Aligned {count} chunks.")


def cmd_align_all(args):
    """Align all unaligned chunks in batches."""
    log.info("Starting full alignment pass...")
    count = align_all_unaligned(batch_size=args.batch_size)
    log.info(f"Done. Aligned {count} total chunks.")


def cmd_status(args):
    """Show alignment coverage statistics."""
    ensure_standards_schema()
    stats = alignment_status()
    print("\n=== Standards Alignment Status ===")
    for key, val in stats.items():
        print(f"  {key}: {val}")

    if stats.get("total_standards", 0) > 0:
        pct = stats.get("embedded_standards", 0) / stats["total_standards"] * 100
        print(f"\n  Standards embedding coverage: {pct:.1f}%")

    if stats.get("total_chunks", 0) > 0:
        aligned = stats.get("aligned_chunks", 0)
        total = stats["total_chunks"]
        pct = aligned / total * 100
        print(f"  Chunk alignment coverage:     {pct:.1f}%")
    print()


def cmd_test_retrieval(args):
    """Test retrieval for a specific standard code."""
    log.info(f"Retrieving content for standard {args.code} (grade={args.grade})...")

    if args.grade:
        # Use the full teaching assignment retrieval
        results = retrieve_for_teaching_assignment(
            standard_codes=[args.code],
            grade=args.grade,
            subject=args.subject or "",
            top_k=args.top_k,
        )
    else:
        results = retrieve_for_standard(
            standard_code=args.code,
            subject=args.subject,
            top_k=args.top_k,
        )

    if not results:
        print(f"\nNo content found aligned to {args.code}")
        return

    print(f"\n=== {len(results)} results for {args.code} ===\n")
    for i, row in enumerate(results, 1):
        print(f"--- Result {i} ---")
        print(f"  Source:    {row.get('source_name', 'N/A')}")
        print(f"  Section:  {row.get('section_heading', 'N/A')}")
        print(f"  Reading:  {row.get('reading_level', 'N/A')}")
        print(f"  Bands:    {row.get('grade_bands', [])}")
        content_preview = (row.get("content") or "")[:200]
        print(f"  Content:  {content_preview}...")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Standards alignment CLI for Lulia"
    )
    sub = parser.add_subparsers(dest="command")

    # embed-standards
    p_embed = sub.add_parser("embed-standards", help="Embed all standards")
    p_embed.add_argument("--batch-size", type=int, default=50)
    p_embed.set_defaults(func=cmd_embed_standards)

    # align
    p_align = sub.add_parser("align", help="Align chunks from a source")
    p_align.add_argument("--source-id", default=None, help="Source UUID")
    p_align.add_argument("--limit", type=int, default=100)
    p_align.set_defaults(func=cmd_align)

    # align-all
    p_all = sub.add_parser("align-all", help="Align all unaligned chunks")
    p_all.add_argument("--batch-size", type=int, default=100)
    p_all.set_defaults(func=cmd_align_all)

    # status
    p_status = sub.add_parser("status", help="Show alignment coverage")
    p_status.set_defaults(func=cmd_status)

    # test-retrieval
    p_test = sub.add_parser("test-retrieval", help="Test content retrieval")
    p_test.add_argument("--code", required=True, help="Standard code (e.g. 5-PS1-1)")
    p_test.add_argument("--grade", default=None, help="Grade level (e.g. 5, K)")
    p_test.add_argument("--subject", default=None, help="Subject filter")
    p_test.add_argument("--top-k", type=int, default=10)
    p_test.set_defaults(func=cmd_test_retrieval)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
