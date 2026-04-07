"""
OpenStax Ingestion CLI — sync catalog, clone repos, parse + embed books.

Usage:
  docker compose exec api python scripts/ingest_openstax.py sync-catalog
  docker compose exec api python scripts/ingest_openstax.py sync-repos [--content-dir /data/content/openstax]
  docker compose exec api python scripts/ingest_openstax.py parse --book-slug=college-algebra-2e
  docker compose exec api python scripts/ingest_openstax.py embed --book-slug=college-algebra-2e
  docker compose exec api python scripts/ingest_openstax.py sync-all [--content-dir ...] [--max-books 5]
"""
import argparse
import logging
import sys

# Setup path for imports
sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection
# Imports from new canonical location (content_sources.openstax).
# The old openstax_ingestion module re-exports these for backwards compat.
from src.lms_agents.tools.content_sources.openstax import (
    get_subject_grade,
    ingest_book,
    parse_book,
    read_license,
    sync_openstax_catalog,
    sync_openstax_repo,
)
# Legacy wrapper kept for the embed command path
from src.lms_agents.tools.openstax_ingestion import chunk_and_embed_book

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DEFAULT_CONTENT_DIR = "/data/content/openstax"


def cmd_sync_catalog(args):
    """Sync the OpenStax approved book catalog."""
    result = sync_openstax_catalog()
    log.info(f"Catalog sync complete: {result}")


def cmd_sync_repos(args):
    """Clone or pull all repos in the catalog."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT repository_name FROM openstax_catalog ORDER BY repository_name")
    repos = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    log.info(f"Syncing {len(repos)} repositories...")
    for repo_name in repos:
        result = sync_openstax_repo(args.content_dir, repo_name)
        log.info(f"  {repo_name}: {result['status']}")


def cmd_parse(args):
    """Parse a single book and print module info."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT repository_name, book_uuid FROM openstax_catalog WHERE book_slug = %s",
        (args.book_slug,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        log.error(f"Book slug '{args.book_slug}' not found in catalog. Run sync-catalog first.")
        sys.exit(1)

    repo_name, book_uuid = row
    repo_path = f"{args.content_dir}/{repo_name}"

    modules = parse_book(repo_path, args.book_slug)
    log.info(f"\nParsed {len(modules)} modules from {args.book_slug}:")
    for mod in modules:
        word_count = len(mod["text"].split())
        obj_count = len(mod.get("learning_objectives", []))
        log.info(
            f"  Ch{mod['chapter']:>2} | {mod['module_id']:12s} | "
            f"{word_count:5d} words | {obj_count} objectives | {mod['title'][:60]}"
        )


def cmd_embed(args):
    """Parse and embed a single book."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT repository_name, book_uuid FROM openstax_catalog WHERE book_slug = %s",
        (args.book_slug,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        log.error(f"Book slug '{args.book_slug}' not found in catalog. Run sync-catalog first.")
        sys.exit(1)

    repo_name, book_uuid = row
    repo_path = f"{args.content_dir}/{repo_name}"
    subject, grade = get_subject_grade(args.book_slug)

    # Ensure repo is cloned
    sync_result = sync_openstax_repo(args.content_dir, repo_name)
    license_str = sync_result.get("license")

    modules = parse_book(repo_path, args.book_slug)
    if not modules:
        log.error(f"No modules parsed from {args.book_slug}")
        sys.exit(1)

    result = chunk_and_embed_book(
        modules, args.book_slug, book_uuid, license_str, subject, grade,
    )
    log.info(f"Embed complete: {result}")


def cmd_sync_all(args):
    """Full pipeline: catalog -> repos -> parse+embed for each book."""
    # 1. Sync catalog
    log.info("=" * 60)
    log.info("Step 1: Syncing catalog")
    log.info("=" * 60)
    sync_openstax_catalog()

    # 2. Get book list from catalog
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT book_slug, repository_name, book_uuid FROM openstax_catalog ORDER BY book_slug"
    )
    books = cur.fetchall()
    cur.close()
    conn.close()

    if args.max_books:
        books = books[:args.max_books]

    log.info(f"\nWill process {len(books)} books")

    # 3. Clone/pull repos
    log.info("=" * 60)
    log.info("Step 2: Syncing repositories")
    log.info("=" * 60)
    seen_repos = set()
    for slug, repo_name, book_uuid in books:
        if repo_name not in seen_repos:
            sync_openstax_repo(args.content_dir, repo_name)
            seen_repos.add(repo_name)

    # 4. Parse + embed each book
    log.info("=" * 60)
    log.info("Step 3: Parsing and embedding books")
    log.info("=" * 60)
    total_sources = 0
    total_chunks = 0

    for slug, repo_name, book_uuid in books:
        log.info(f"\n{'─' * 40}")
        log.info(f"Book: {slug}")
        log.info(f"{'─' * 40}")

        repo_path = f"{args.content_dir}/{repo_name}"
        subject, grade = get_subject_grade(slug)

        # Read license from repo
        license_str = None
        import os
        for lic_name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
            lic_path = os.path.join(repo_path, lic_name)
            if os.path.isfile(lic_path):
                with open(lic_path, "r", encoding="utf-8", errors="replace") as f:
                    license_str = f.read()[:2000]
                break

        modules = parse_book(repo_path, slug)
        if not modules:
            log.warning(f"  No modules found for {slug}, skipping")
            continue

        result = chunk_and_embed_book(
            modules, slug, book_uuid, license_str, subject, grade,
        )
        total_sources += result["sources_created"]
        total_chunks += result["chunks_created"]

    log.info(f"\n{'=' * 60}")
    log.info(f"DONE: {total_sources} sources, {total_chunks} chunks across {len(books)} books")
    log.info(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="OpenStax Ingestion Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync-catalog
    subparsers.add_parser("sync-catalog", help="Fetch and store the OpenStax book catalog")

    # sync-repos
    p_repos = subparsers.add_parser("sync-repos", help="Clone/pull all repos in catalog")
    p_repos.add_argument("--content-dir", default=DEFAULT_CONTENT_DIR)

    # parse
    p_parse = subparsers.add_parser("parse", help="Parse a single book (dry run)")
    p_parse.add_argument("--book-slug", required=True)
    p_parse.add_argument("--content-dir", default=DEFAULT_CONTENT_DIR)

    # embed
    p_embed = subparsers.add_parser("embed", help="Parse + embed a single book")
    p_embed.add_argument("--book-slug", required=True)
    p_embed.add_argument("--content-dir", default=DEFAULT_CONTENT_DIR)

    # sync-all
    p_all = subparsers.add_parser("sync-all", help="Full pipeline: catalog + repos + embed all")
    p_all.add_argument("--content-dir", default=DEFAULT_CONTENT_DIR)
    p_all.add_argument("--max-books", type=int, default=None, help="Limit number of books to process")

    args = parser.parse_args()

    commands = {
        "sync-catalog": cmd_sync_catalog,
        "sync-repos": cmd_sync_repos,
        "parse": cmd_parse,
        "embed": cmd_embed,
        "sync-all": cmd_sync_all,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
