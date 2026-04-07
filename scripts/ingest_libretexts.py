"""
LibreTexts K-12 Content Ingestion — crawls k12.libretexts.org and ingests
textbook content into the RAG knowledge base (pgvector).

This gives the AI ground truth for generating deterministic, accurate content.

Usage:
  docker compose exec api python scripts/ingest_libretexts.py [--subject Mathematics] [--max-pages 50]

Subjects available: Mathematics, Science_and_Technology, Economics, Geography,
  Human_Biology, United_States_Government, Spelling, Health, Philosophy
"""
import argparse
import logging
import sys
import time

# Setup path for imports
sys.path.insert(0, "/app")

# Import from new canonical location (content_sources.libretexts)
from src.lms_agents.tools.content_sources.libretexts import (
    LIBRARIES,
    extract_page_content,
    get_leaf_page_urls,
    get_subject_bookshelves,
    ingest_page,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest LibreTexts content into RAG KB")
    parser.add_argument("--library", default="k12", help="Library: k12, bio, chem, phys, socialsci, or 'all'")
    parser.add_argument("--subject", help="Filter to subject path containing this string")
    parser.add_argument("--max-pages", type=int, default=50, help="Max leaf pages per subject")
    parser.add_argument("--list", action="store_true", help="List available libraries and subjects")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between page fetches")
    args = parser.parse_args()

    if args.list:
        for lib_name, lib_data in LIBRARIES.items():
            print(f"\n{lib_name} ({lib_data['base_url']}):")
            for subj, meta in lib_data["subjects"].items():
                print(f"  {subj}  →  Grade {meta['grade']}, {meta['subject']}")
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

        log.info(f"\n{'='*60}")
        log.info(f"Library: {lib_name} ({base_url}) — {len(subjects)} subjects")
        log.info(f"{'='*60}")

        for subject_path, meta in subjects.items():
            subject_display = subject_path.replace("_", " ").replace("/", " > ")
            log.info(f"\n  Subject: {subject_display} (Grade {meta['grade']}, {meta['subject']})")

            page_urls = get_leaf_page_urls(subject_path, base_url=base_url)
            log.info(f"  Found {len(page_urls)} leaf pages")

            for i, url in enumerate(page_urls[:args.max_pages]):
                page_title = url.split("/")[-1].replace("%3A_", ": ").replace("_", " ").replace("%", "")
                lib_label = lib_name.upper() if lib_name != "k12" else "K-12"
                label = f"LibreTexts {lib_label} — {subject_display} — {page_title}"

                log.info(f"  [{i+1}/{min(len(page_urls), args.max_pages)}] {page_title[:60]}...")
                n = ingest_page(url, meta["subject"], meta["grade"], label, browser=browser)
                total_chunks += n
                total_pages += 1
                log.info(f"    → {n} chunks ingested")

                time.sleep(args.delay)

    browser.close()
    log.info(f"\n{'='*60}")
    log.info(f"DONE: Ingested {total_pages} pages → {total_chunks} chunks")
    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()
