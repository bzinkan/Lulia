"""
Library of Congress content source adapter.

The LoC JSON API provides access to primary sources — photographs, documents,
manuscripts, newspapers, maps — all free and mostly public domain.

Perfect for filling the Social Studies and ELA gaps in Lulia's content.

No API key required. Rate limit: 20 requests/minute. Use 2s delay between requests.

Usage:
    from src.lms_agents.tools.content_sources.loc import ingest_topic
    ingest_topic("Civil War", grade="8", subject="Social Studies", max_items=20)
"""
import logging
import re
import time
from typing import Optional

import httpx

from src.lms_agents.tools.content_ingestion_core import ingest_sections, source_exists

log = logging.getLogger(__name__)

BASE_URL = "https://www.loc.gov"
DELAY = 2.5  # seconds between requests (stay under 20/min rate limit)

# Curated topic → search query mapping for common K-12 US history/social studies units
CURATED_TOPICS = {
    "American Revolution": {
        "query": "american revolution",
        "grade_band": "8",
        "subject": "Social Studies",
    },
    "Civil War": {
        "query": "civil war",
        "grade_band": "8",
        "subject": "Social Studies",
    },
    "Westward Expansion": {
        "query": "westward expansion",
        "grade_band": "8",
        "subject": "Social Studies",
    },
    "Industrial Revolution": {
        "query": "industrial revolution",
        "grade_band": "10",
        "subject": "Social Studies",
    },
    "Great Depression": {
        "query": "great depression dust bowl",
        "grade_band": "11",
        "subject": "Social Studies",
    },
    "World War I": {
        "query": "world war 1",
        "grade_band": "11",
        "subject": "Social Studies",
    },
    "World War II": {
        "query": "world war 2",
        "grade_band": "11",
        "subject": "Social Studies",
    },
    "Civil Rights Movement": {
        "query": "civil rights movement",
        "grade_band": "11",
        "subject": "Social Studies",
    },
    "Great Migration": {
        "query": "great migration african american",
        "grade_band": "11",
        "subject": "Social Studies",
    },
    "Constitution": {
        "query": "constitution founding fathers",
        "grade_band": "11",
        "subject": "Social Studies",
    },
    "Immigration": {
        "query": "immigration ellis island",
        "grade_band": "8",
        "subject": "Social Studies",
    },
    "Native American History": {
        "query": "native american indigenous",
        "grade_band": "8",
        "subject": "Social Studies",
    },
    "Slavery and Abolition": {
        "query": "slavery abolition frederick douglass",
        "grade_band": "8",
        "subject": "Social Studies",
    },
    "Women's Suffrage": {
        "query": "womens suffrage voting rights",
        "grade_band": "8",
        "subject": "Social Studies",
    },
    "Cold War": {
        "query": "cold war",
        "grade_band": "11",
        "subject": "Social Studies",
    },
}


def search_loc(query: str, page: int = 1, per_page: int = 20) -> list[dict]:
    """
    Search the Library of Congress API for items matching a query.
    Returns a list of items with metadata.
    """
    try:
        resp = httpx.get(
            f"{BASE_URL}/search/",
            params={
                "q": query,
                "fo": "json",
                "c": per_page,
                "sp": page,
                "at": "results,pagination",  # only fetch what we need
            },
            timeout=15,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        log.warning(f"[LoC] Search failed for '{query}': {e}")
        return []


def get_item_details(item_url: str) -> Optional[dict]:
    """Fetch full details for a single LoC item. item_url is from search results."""
    # Append fo=json if not already there
    url = item_url
    if "fo=json" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}fo=json"
    try:
        resp = httpx.get(url, timeout=15, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning(f"[LoC] Item fetch failed for {url}: {e}")
        return None


def _extract_text_content(item: dict) -> str:
    """
    Extract meaningful text content from a LoC item for RAG.
    Combines title, description, notes, subjects, dates.
    """
    parts = []

    title = item.get("title", "")
    if title:
        parts.append(f"Title: {title}")

    # Description can be a string or list
    description = item.get("description", "")
    if isinstance(description, list):
        description = " ".join(str(d) for d in description if d)
    if description:
        parts.append(f"Description: {description}")

    # Notes often have rich historical context
    notes = item.get("notes", [])
    if isinstance(notes, list):
        for note in notes:
            if note and isinstance(note, str):
                parts.append(f"Note: {note}")

    # Subject headings — useful for standards tagging
    subjects = item.get("subject", [])
    if isinstance(subjects, list) and subjects:
        parts.append(f"Subjects: {', '.join(str(s) for s in subjects if s)}")

    # Dates
    date = item.get("date", "")
    if date:
        parts.append(f"Date: {date}")

    # Original format (photograph, manuscript, map, etc.)
    original_format = item.get("original_format", [])
    if isinstance(original_format, list) and original_format:
        parts.append(f"Format: {', '.join(str(f) for f in original_format if f)}")

    return "\n\n".join(parts)


def _check_rights(item: dict) -> tuple[bool, str]:
    """
    Check if an item is safe for commercial/educational use.
    Returns (is_safe, rights_string).
    """
    rights = item.get("rights", "")
    if isinstance(rights, list):
        rights = " ".join(str(r) for r in rights)
    rights_lower = (rights or "").lower()

    # Public domain or no known restrictions = safe
    safe_keywords = ["public domain", "no known restrictions", "cc0", "creative commons"]
    if any(kw in rights_lower for kw in safe_keywords):
        return True, rights

    # If rights field is empty, default to safe (most LoC is public domain)
    if not rights:
        return True, "unknown (default: public domain)"

    # Known restricted
    restricted_keywords = ["copyright", "restricted", "all rights reserved"]
    if any(kw in rights_lower for kw in restricted_keywords):
        return False, rights

    return True, rights


def ingest_topic(
    topic_name: str,
    query: Optional[str] = None,
    grade: str = "8",
    subject: str = "Social Studies",
    max_items: int = 20,
) -> dict:
    """
    Ingest LoC content for a topic into Lulia's RAG knowledge base.

    Args:
        topic_name: Human-readable topic name (e.g., "Civil War")
        query: Search query (defaults to topic_name.lower() if not provided)
        grade: Grade level for tagging
        subject: Subject for tagging
        max_items: Max number of items to ingest (default 20)

    Returns:
        Dict with ingestion stats.
    """
    if not query:
        # Check curated topics first
        curated = CURATED_TOPICS.get(topic_name)
        if curated:
            query = curated["query"]
            grade = curated.get("grade_band", grade)
            subject = curated.get("subject", subject)
        else:
            query = topic_name.lower()

    log.info(f"[LoC] Ingesting topic '{topic_name}' (query: '{query}', max: {max_items})")

    # Search
    results = search_loc(query, per_page=max_items)
    if not results:
        log.warning(f"[LoC] No results for '{query}'")
        return {"topic": topic_name, "ingested": 0, "skipped": 0, "status": "no_results"}

    ingested = 0
    skipped = 0
    restricted = 0

    for item in results[:max_items]:
        item_id = item.get("id", "")
        item_title = item.get("title", "Untitled")[:80]

        # Check rights
        is_safe, rights_str = _check_rights(item)
        if not is_safe:
            log.info(f"[LoC]   Skipped (restricted): {item_title}")
            restricted += 1
            continue

        # Build a source name that's unique per item
        source_name = f"Library of Congress — {topic_name} — {item_title}"

        # Idempotent check
        if source_exists(source_name):
            skipped += 1
            continue

        # Extract content
        content_text = _extract_text_content(item)
        if not content_text or len(content_text) < 50:
            skipped += 1
            continue

        # Prepare sections for ingestion
        sections = [{
            "page": None,
            "heading": topic_name,
            "text": content_text,
        }]

        # Get item URL for original_path
        item_url = item.get("url", item.get("id", ""))

        try:
            result = ingest_sections(
                sections=sections,
                name=source_name,
                subject=subject,
                grade_level=grade,
                upload_lane="loc",
                file_type="primary_source",
                original_path=item_url,
            )
            if result.get("chunk_count", 0) > 0:
                ingested += 1
                log.info(f"[LoC]   ✓ {item_title}")
            else:
                skipped += 1
        except Exception as e:
            log.warning(f"[LoC]   Failed to ingest {item_title}: {e}")
            skipped += 1

        # Rate limit: stay under 20/min
        time.sleep(DELAY)

    log.info(f"[LoC] Done: {ingested} ingested, {skipped} skipped, {restricted} restricted")
    return {
        "topic": topic_name,
        "query": query,
        "ingested": ingested,
        "skipped": skipped,
        "restricted": restricted,
        "total_results": len(results),
        "status": "complete",
    }


def ingest_all_curated() -> dict:
    """Ingest all 15 curated US history topics."""
    total = {"topics": 0, "ingested": 0, "skipped": 0, "restricted": 0}
    for topic_name in CURATED_TOPICS:
        result = ingest_topic(topic_name)
        total["topics"] += 1
        total["ingested"] += result.get("ingested", 0)
        total["skipped"] += result.get("skipped", 0)
        total["restricted"] += result.get("restricted", 0)
    log.info(f"[LoC] All curated topics complete: {total}")
    return total
