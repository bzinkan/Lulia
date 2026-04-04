"""
Curriculum Importer — dual pipeline that feeds both RAG KB and Curriculum Calendar.

When a teacher uploads a curriculum/pacing guide:
1. Full text → knowledge ingestion pipeline (RAG KB for agent search)
2. Structured pacing data → curriculum_calendar table (for Planner scheduling)

Uses Claude Haiku to parse document structure and extract:
- Unit names and sequence
- Week numbers or date ranges
- Standards/topics per unit or week
- Assessment weeks
"""
import csv
import io
import json
import logging
import os
import re
from datetime import date, timedelta
from uuid import uuid4

from psycopg2.extras import Json

from src.lms_agents.tools.db import get_connection
from src.lms_agents.tools.knowledge_ingestion import (
    extract_pdf, extract_docx, extract_text, chunk_sections, ingest_file,
)

log = logging.getLogger(__name__)


def parse_pacing_with_claude(full_text: str, subject: str | None = None) -> list[dict]:
    """
    Use Claude Haiku to extract structured pacing data from curriculum text.

    Returns list of dicts:
    [
      {
        "week_number": 1,
        "unit_name": "Place Value and Whole Numbers",
        "topic": "Understanding place value to millions",
        "standards_scheduled": ["4.NBT.1", "4.NBT.2"],
        "is_assessment_week": false,
        "pacing_notes": "Introduce manipulatives"
      },
      ...
    ]
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping pacing extraction")
        return []

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        log.warning(f"Failed to init Anthropic client: {e}")
        return []

    # Truncate to fit context window (~100k chars is safe for Haiku)
    truncated = full_text[:80000]

    prompt = f"""You are a curriculum specialist. Analyze the following curriculum or pacing guide document and extract the weekly pacing schedule.

Subject context: {subject or 'not specified'}

Document text:
{truncated}

Extract a JSON array of weekly entries. Each entry should have:
- "week_number": integer (1-based sequence)
- "unit_name": string (the unit or chapter name)
- "topic": string (specific topic for that week)
- "standards_scheduled": array of standard code strings (e.g. ["4.NF.1", "4.NF.2"])
- "is_assessment_week": boolean (true if this week includes a test/quiz/assessment)
- "pacing_notes": string or null (any special notes like "review week", "field trip", etc.)

If the document uses date ranges instead of week numbers, convert them to sequential week numbers starting from 1.
If standards are referenced by description rather than code, infer the most likely standard codes.
If the document doesn't contain clear weekly pacing, break it into logical units and estimate weeks.

Respond ONLY with the JSON array, no other text."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Extract JSON array from response
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            entries = json.loads(match.group())
            log.info(f"  Extracted {len(entries)} calendar entries from curriculum")
            return entries
        else:
            log.warning("  Could not extract JSON from Claude response")
            return []
    except Exception as e:
        log.warning(f"  Pacing extraction failed: {e}")
        return []


def store_calendar_entries(
    class_id: str,
    entries: list[dict],
    source_upload_id: str | None = None,
    week_start: date | None = None,
) -> int:
    """
    Store parsed pacing entries into curriculum_calendar table.
    Returns number of entries stored.

    If week_start is provided, computes week_start_date for each entry.
    """
    if not entries:
        return 0

    conn = get_connection()
    cur = conn.cursor()
    stored = 0

    try:
        for entry in entries:
            week_num = entry.get("week_number", stored + 1)
            week_start_date = None
            if week_start:
                week_start_date = week_start + timedelta(weeks=week_num - 1)

            cur.execute(
                """INSERT INTO curriculum_calendar
                   (calendar_id, class_id, week_number, week_start_date,
                    unit_name, topic, standards_scheduled, pacing_notes,
                    is_assessment_week, source_upload_id)
                   VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::uuid)""",
                (
                    str(uuid4()),
                    class_id,
                    week_num,
                    week_start_date,
                    entry.get("unit_name"),
                    entry.get("topic"),
                    Json(entry.get("standards_scheduled", [])),
                    entry.get("pacing_notes"),
                    entry.get("is_assessment_week", False),
                    source_upload_id,
                ),
            )
            stored += 1

        conn.commit()
        log.info(f"  Stored {stored} calendar entries for class {class_id}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return stored


def import_curriculum(
    file_path: str,
    file_type: str,
    name: str,
    teacher_id: str,
    class_id: str,
    subject: str | None = None,
    grade_level: str | None = None,
    week_start: date | None = None,
) -> dict:
    """
    Full dual pipeline for curriculum upload:
    1. Ingest into RAG KB (knowledge_sources + knowledge_chunks)
    2. Parse pacing data and store in curriculum_calendar

    Returns dict with both pipeline results.
    """
    log.info(f"Curriculum import: {name} ({file_type}) for class {class_id}")

    # --- Pipeline 1: RAG KB ---
    rag_result = ingest_file(
        file_path=file_path,
        file_type=file_type,
        name=name,
        teacher_id=teacher_id,
        upload_lane="curriculum",
        subject=subject,
        grade_level=grade_level,
    )
    log.info(f"  RAG KB: {rag_result['chunk_count']} chunks")

    # --- Pipeline 2: Curriculum Calendar ---
    # Extract full text for Claude parsing
    if file_type == "pdf":
        sections = extract_pdf(file_path)
    elif file_type in ("docx", "doc"):
        sections = extract_docx(file_path)
    else:
        sections = extract_text(file_path)

    full_text = "\n\n".join(s["text"] for s in sections)
    pacing_entries = parse_pacing_with_claude(full_text, subject)

    calendar_count = store_calendar_entries(
        class_id=class_id,
        entries=pacing_entries,
        source_upload_id=rag_result.get("source_id"),
        week_start=week_start,
    )

    return {
        "source_id": rag_result.get("source_id"),
        "rag_chunks": rag_result.get("chunk_count", 0),
        "rag_embedded": rag_result.get("embedded_count", 0),
        "calendar_entries": calendar_count,
        "status": "complete",
    }


def import_csv_pacing(
    csv_content: str,
    class_id: str,
    week_start: date | None = None,
) -> dict:
    """
    Import pacing data from CSV.

    Expected columns: week_number, unit_name, topic, standards (comma-separated), assessment, notes
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    entries = []

    for row in reader:
        # Normalize column names (strip whitespace, lowercase)
        row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

        standards_raw = row.get("standards", row.get("standards_scheduled", ""))
        standards = [s.strip() for s in standards_raw.split(",") if s.strip()]

        assessment_raw = row.get("assessment", row.get("is_assessment_week", ""))
        is_assessment = assessment_raw.lower() in ("true", "yes", "1", "x", "assessment")

        entries.append({
            "week_number": int(row.get("week_number", row.get("week", len(entries) + 1))),
            "unit_name": row.get("unit_name", row.get("unit", "")),
            "topic": row.get("topic", ""),
            "standards_scheduled": standards,
            "is_assessment_week": is_assessment,
            "pacing_notes": row.get("notes", row.get("pacing_notes", None)),
        })

    count = store_calendar_entries(
        class_id=class_id,
        entries=entries,
        week_start=week_start,
    )

    return {"calendar_entries": count, "status": "complete"}
