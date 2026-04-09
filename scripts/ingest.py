"""
Unified content ingestion CLI.

Usage:
  python scripts/ingest.py openstax sync-catalog
  python scripts/ingest.py openstax sync-repos [--content-dir ...]
  python scripts/ingest.py openstax sync-all [--content-dir ...] [--max-books 5]
  python scripts/ingest.py libretexts --library k12 [--max-pages 20]
  python scripts/ingest.py libretexts --library all
  python scripts/ingest.py loc --topic "Civil War" [--max-items 20]
  python scripts/ingest.py loc --all-curated
  python scripts/ingest.py status
"""
import argparse
import logging
import os
import sys
import time

sys.path.insert(0, "/app")

from src.lms_agents.tools.db import get_connection

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DEFAULT_OPENSTAX_DIR = "/data/content/openstax"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def handle_status(args):
    """Show chunk counts per upload_lane."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT upload_lane,
               COUNT(DISTINCT source_id) AS sources,
               SUM(chunk_count) AS chunks
        FROM knowledge_sources
        GROUP BY upload_lane
        ORDER BY upload_lane
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        log.info("No ingested sources found.")
        return

    log.info(f"{'Lane':<20} {'Sources':>8} {'Chunks':>8}")
    log.info("-" * 38)
    total_sources = 0
    total_chunks = 0
    for lane, sources, chunks in rows:
        chunks = chunks or 0
        log.info(f"{lane:<20} {sources:>8} {chunks:>8}")
        total_sources += sources
        total_chunks += chunks
    log.info("-" * 38)
    log.info(f"{'TOTAL':<20} {total_sources:>8} {total_chunks:>8}")


# ---------------------------------------------------------------------------
# OpenStax
# ---------------------------------------------------------------------------

def handle_openstax(args):
    """Handle openstax subcommands."""
    from src.lms_agents.tools.content_sources.openstax import (
        get_subject_grade,
        ingest_book,
        parse_book,
        read_license,
        sync_openstax_catalog,
        sync_openstax_repo,
    )

    if args.openstax_cmd == "sync-catalog":
        result = sync_openstax_catalog()
        log.info(f"Catalog sync complete: {result}")

    elif args.openstax_cmd == "sync-repos":
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

    elif args.openstax_cmd == "sync-all":
        # 1. Sync catalog
        log.info("=" * 60)
        log.info("Step 1: Syncing catalog")
        log.info("=" * 60)
        sync_openstax_catalog()

        # 2. Get book list
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
            license_str = read_license(repo_path)

            result = ingest_book(
                repo_path, slug, book_uuid,
                content_dir=args.content_dir,
                license_str=license_str,
            )
            total_sources += result["sources_created"]
            total_chunks += result["chunks_created"]

        log.info(f"\n{'=' * 60}")
        log.info(f"DONE: {total_sources} sources, {total_chunks} chunks across {len(books)} books")
        log.info(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# LibreTexts
# ---------------------------------------------------------------------------

def handle_libretexts(args):
    """Handle libretexts ingestion."""
    from src.lms_agents.tools.content_sources.libretexts import (
        LIBRARIES,
        get_leaf_page_urls,
        ingest_page,
    )

    if args.list_subjects:
        for lib_name, lib_data in LIBRARIES.items():
            print(f"\n{lib_name} ({lib_data['base_url']}):")
            for subj, meta in lib_data["subjects"].items():
                print(f"  {subj}  ->  Grade {meta['grade']}, {meta['subject']}")
        return

    libs_to_run = list(LIBRARIES.keys()) if args.library == "all" else [args.library]

    total_chunks = 0
    total_pages = 0

    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    log.info("Browser launched for content extraction")

    for lib_name in libs_to_run:
        lib = LIBRARIES.get(lib_name)
        if not lib:
            log.error(f"Unknown library: {lib_name}. Use --list to see options.")
            continue

        base_url = lib["base_url"]
        subjects = lib["subjects"]
        if args.subject:
            subjects = {k: v for k, v in subjects.items() if args.subject.lower() in k.lower()}

        log.info(f"\n{'=' * 60}")
        log.info(f"Library: {lib_name} ({base_url}) — {len(subjects)} subjects")
        log.info(f"{'=' * 60}")

        for subject_path, meta in subjects.items():
            subject_display = subject_path.replace("_", " ").replace("/", " > ")
            log.info(f"\n  Subject: {subject_display} (Grade {meta['grade']}, {meta['subject']})")

            page_urls = get_leaf_page_urls(subject_path, base_url=base_url)
            log.info(f"  Found {len(page_urls)} leaf pages")

            for i, url in enumerate(page_urls[:args.max_pages]):
                page_title = url.split("/")[-1].replace("%3A_", ": ").replace("_", " ").replace("%", "")
                lib_label = lib_name.upper() if lib_name != "k12" else "K-12"
                label = f"LibreTexts {lib_label} — {subject_display} — {page_title}"

                log.info(f"  [{i + 1}/{min(len(page_urls), args.max_pages)}] {page_title[:60]}...")
                n = ingest_page(url, meta["subject"], meta["grade"], label, browser=browser)
                total_chunks += n
                total_pages += 1
                log.info(f"    -> {n} chunks ingested")

                time.sleep(args.delay)

    browser.close()
    log.info(f"\n{'=' * 60}")
    log.info(f"DONE: Ingested {total_pages} pages -> {total_chunks} chunks")
    log.info(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def handle_loc(args):
    """Library of Congress primary source ingestion."""
    from src.lms_agents.tools.content_sources import loc

    if getattr(args, "list_topics", False):
        print("Curated LoC topics:")
        for name, meta in loc.CURATED_TOPICS.items():
            print(f"  {name}  (grade {meta['grade_band']}, {meta['subject']})")
        return

    if getattr(args, "all_curated", False):
        result = loc.ingest_all_curated()
        log.info(f"All curated topics complete: {result}")
        return

    if args.topic:
        result = loc.ingest_topic(
            topic_name=args.topic,
            query=args.query,
            grade=args.grade,
            subject=args.subject,
            max_items=args.max_items,
        )
        log.info(f"Topic '{args.topic}' complete: {result}")
        return

    log.error("Specify --topic, --all-curated, or --list-topics")


SOURCES = {
    "openstax": handle_openstax,
    "libretexts": handle_libretexts,
    "loc": handle_loc,
    "status": handle_status,
}


def main():
    parser = argparse.ArgumentParser(description="Unified Content Ingestion CLI")
    subparsers = parser.add_subparsers(dest="source", required=True)

    # status
    subparsers.add_parser("status", help="Show ingestion status by lane")

    # openstax
    p_os = subparsers.add_parser("openstax", help="OpenStax ingestion")
    os_sub = p_os.add_subparsers(dest="openstax_cmd", required=True)

    os_sub.add_parser("sync-catalog", help="Fetch and store the OpenStax book catalog")

    p_repos = os_sub.add_parser("sync-repos", help="Clone/pull all repos in catalog")
    p_repos.add_argument("--content-dir", default=DEFAULT_OPENSTAX_DIR)

    p_all = os_sub.add_parser("sync-all", help="Full pipeline: catalog + repos + embed all")
    p_all.add_argument("--content-dir", default=DEFAULT_OPENSTAX_DIR)
    p_all.add_argument("--max-books", type=int, default=None, help="Limit number of books")

    # libretexts
    p_lt = subparsers.add_parser("libretexts", help="LibreTexts ingestion")
    p_lt.add_argument("--library", default="k12", help="Library: k12, bio, chem, phys, socialsci, or 'all'")
    p_lt.add_argument("--subject", help="Filter to subject path containing this string")
    p_lt.add_argument("--max-pages", type=int, default=50, help="Max leaf pages per subject")
    p_lt.add_argument("--list", dest="list_subjects", action="store_true", help="List available libraries and subjects")
    p_lt.add_argument("--delay", type=float, default=2.0, help="Seconds between page fetches")

    # loc (Library of Congress)
    p_loc = subparsers.add_parser("loc", help="Library of Congress primary source ingestion")
    p_loc.add_argument("--topic", help="Topic name to ingest (e.g., 'Civil War')")
    p_loc.add_argument("--query", help="Custom search query (defaults to topic name)")
    p_loc.add_argument("--grade", default="8", help="Grade level for tagging")
    p_loc.add_argument("--subject", default="Social Studies", help="Subject for tagging")
    p_loc.add_argument("--max-items", type=int, default=20, help="Max items to ingest per topic")
    p_loc.add_argument("--all-curated", action="store_true", help="Ingest all 15 curated US history topics")
    p_loc.add_argument("--list-topics", action="store_true", help="List curated topics")

    args = parser.parse_args()
    SOURCES[args.source](args)


if __name__ == "__main__":
    main()
