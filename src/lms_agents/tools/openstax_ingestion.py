"""
OpenStax Ingestion Pipeline — backwards-compatible wrapper.

DEPRECATED: Import from src.lms_agents.tools.content_sources.openstax instead.
This module re-exports all public symbols for existing callers.
"""
import logging

log = logging.getLogger(__name__)

# Re-export everything from the new location for backwards compatibility
from src.lms_agents.tools.content_sources.openstax import (  # noqa: F401
    BOOK_SUBJECT_MAP,
    CATALOG_URL,
    NS_CNXML,
    NS_COLLXML,
    NS_MD,
    get_subject_grade,
    ingest_book,
    parse_book,
    read_license,
    sync_openstax_catalog,
    sync_openstax_repo,
)

SYSTEM_TEACHER_ID = "00000000-0000-0000-0000-000000000000"


def chunk_and_embed_book(
    parsed_modules: list[dict],
    book_slug: str,
    book_uuid: str | None,
    license_str: str | None,
    subject: str,
    grade: str,
) -> dict:
    """
    DEPRECATED: Use content_sources.openstax.ingest_book() instead.

    Kept for backwards compatibility with scripts/ingest_openstax.py.
    Delegates to ingest_book() which uses the shared core pipeline.
    """
    log.warning(
        "chunk_and_embed_book() is deprecated — use "
        "content_sources.openstax.ingest_book() instead"
    )
    # We need a repo_path to call ingest_book, but this legacy function
    # receives pre-parsed modules. Replicate the old behavior using the core.
    from src.lms_agents.tools.content_ingestion_core import ingest_sections, source_exists

    if not parsed_modules:
        log.warning(f"No modules to embed for {book_slug}")
        return {"sources_created": 0, "chunks_created": 0}

    sources_created = 0
    chunks_created = 0

    for mod in parsed_modules:
        chapter_label = mod.get("chapter_title") or f"Ch {mod['chapter']}"
        source_name = f"OpenStax \u2014 {book_slug} \u2014 {chapter_label} \u2014 {mod['title']}"

        if source_exists(source_name):
            log.info(f"  Skipping (exists): {mod['module_id']}")
            continue

        heading = f"{chapter_label} > {mod['title']}"
        sections = [{"page": None, "heading": heading, "text": mod["text"]}]

        result = ingest_sections(
            sections=sections,
            name=source_name,
            subject=subject,
            grade_level=grade,
            upload_lane="openstax",
            file_type="cnxml",
            original_path=f"openstax/{book_slug}/{mod['module_id']}",
        )

        if result["status"] == "complete":
            sources_created += 1
            chunks_created += result["chunk_count"]

    # Update license in catalog if available
    if license_str:
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE openstax_catalog SET license = %s WHERE book_slug = %s",
                (license_str, book_slug),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    log.info(
        f"  Book {book_slug}: {sources_created} sources, "
        f"{chunks_created} chunks total"
    )
    return {"sources_created": sources_created, "chunks_created": chunks_created}
