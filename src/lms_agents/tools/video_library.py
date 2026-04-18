"""
Video Library tools — transcript indexing, classification, and standards sync.

Bridges the Video Library feature with Lulia's existing knowledge/alignment
infrastructure. Every video in the library dual-indexes: one row in `videos`
(library metadata) + chunked transcript in `knowledge_sources` / `knowledge_chunks`
with `upload_lane='video_library'` so the transcript is searchable via the
existing RAG pipeline and standards alignment.

Three public functions:

    index_video_transcript(video_id) — chunks + embeds the transcript via
        content_ingestion_core.ingest_sections(). Idempotent.

    classify_video(video_id) — uses Haiku to infer grade_level, subject,
        domain, grade_bands, reading_level from the transcript. Merge-safe:
        only writes fields that are currently NULL.

    sync_video_standards(video_id) — reads alignment_scores from the video's
        chunks (after alignment has run) and upserts into video_standards
        join table so the library picker can filter by standard code.

Invariants:
    - reference_metadata on knowledge_chunks is NEVER touched. All writes go
      through ingest_sections() which only populates alignment_scores /
      reading_level / grade_bands / standards_tags — all of which are
      already merge-safe from Phase 24 work.
    - Existing videos table values are merge-safe: classify_video() only
      fills NULL fields, never overwrites manually-set values.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.content_ingestion_core import ingest_sections
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

HAIKU = "claude-haiku-4-5-20251001"

# How many transcript characters to send to Haiku for classification
CLASSIFY_MAX_CHARS = 4000

# How many top-aligned standards to mirror into video_standards
SYNC_STANDARDS_LIMIT = 15


# ---------------------------------------------------------------------------
# Phase 2a: Transcript indexing
# ---------------------------------------------------------------------------

def _fetch_video(video_id: str) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """SELECT video_id, teacher_id, class_id, title, transcript_text,
                      grade_level, subject, domain, grade_bands, reading_level,
                      scope, hosting_type, source_lane
               FROM videos WHERE video_id = %s::uuid""",
            (video_id,),
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def _split_transcript_into_sections(
    transcript: str, title: str = "", chars_per_section: int = 1200
) -> list[dict]:
    """Break a transcript into roughly-1200-char sections on sentence boundaries.

    Each section becomes one chunk input to ingest_sections(). We keep sections
    small so the downstream standards alignment (which uses top-20 retrieval)
    has tight, topic-focused candidates.
    """
    if not transcript or not transcript.strip():
        return []

    # Simple sentence-ish splitter — good enough for transcripts
    sentences = []
    current = []
    for line in transcript.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        for part in line.replace("! ", "!|").replace("? ", "?|").replace(". ", ".|").split("|"):
            if part.strip():
                sentences.append(part.strip())

    sections: list[dict] = []
    buf: list[str] = []
    buf_len = 0
    page = 1
    for s in sentences:
        if buf_len + len(s) + 1 > chars_per_section and buf:
            sections.append({
                "page": page,
                "heading": title if page == 1 else "",
                "text": " ".join(buf).strip(),
            })
            page += 1
            buf, buf_len = [], 0
        buf.append(s)
        buf_len += len(s) + 1
    if buf:
        sections.append({
            "page": page,
            "heading": title if page == 1 else "",
            "text": " ".join(buf).strip(),
        })
    return sections


def index_video_transcript(video_id: str) -> dict:
    """Chunk + embed the video's transcript into knowledge_sources/chunks.

    Idempotent: the ingest_sections() helper uses deterministic `name` for
    dedup, so re-running skips videos that are already indexed.

    Returns:
        dict with source_id, chunk_count, embedded_count, status
    """
    video = _fetch_video(video_id)
    if not video:
        return {"status": "video_not_found", "video_id": video_id}

    transcript = (video.get("transcript_text") or "").strip()
    if not transcript:
        return {"status": "no_transcript", "video_id": video_id}

    sections = _split_transcript_into_sections(transcript, title=video.get("title") or "")
    if not sections:
        return {"status": "no_sections", "video_id": video_id}

    # Deterministic source name for idempotency — matches ingest_sections convention
    source_name = f"video_library — {video_id}"

    scope = video.get("scope") or "teacher"
    # Teacher-scoped uploads land on knowledge_sources.scope='teacher'
    # Public library videos land on scope='class' so they surface as shared content
    # (ingest_sections accepts 'class' or 'teacher' only)
    ks_scope = "teacher" if scope == "teacher" else "class"

    result = ingest_sections(
        sections=sections,
        name=source_name,
        teacher_id=str(video["teacher_id"]) if video.get("teacher_id") else "00000000-0000-0000-0000-000000000000",
        subject=video.get("subject"),
        grade_level=video.get("grade_level"),
        upload_lane="video_library",
        file_type="video_transcript",
        original_path=f"videos/{video_id}",
        class_id=str(video["class_id"]) if video.get("class_id") else None,
        scope=ks_scope,
    )
    log.info(
        "Video transcript indexed: video_id=%s chunks=%s status=%s",
        video_id, result.get("chunk_count"), result.get("status"),
    )
    return result


# ---------------------------------------------------------------------------
# Phase 2b: Haiku classification
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """You are classifying an educational video transcript for a K-12 library.

Transcript (first {char_count} characters):
---
{transcript}
---

Return ONLY a JSON object with these keys:
{{
  "grade_level": "K" | "1" | "2" | ... | "12"  (best single grade this targets),
  "subject":     "Math" | "English Language Arts" | "Science" | "Social Studies"
                 | "Art" | "Music" | "PE" | "SEL" | "General",
  "domain":      a short phrase like "Fractions", "Photosynthesis",
                 "American Revolution", "Reading Comprehension" — the specific
                 topic within the subject,
  "grade_bands": array from ["K-2","3-5","6-8","9-12"] — any bands this content
                 is appropriate for (one content piece can span multiple bands
                 if vocabulary and complexity support it),
  "reading_level": numeric Flesch-Kincaid grade estimate based on vocabulary
                   and sentence complexity (e.g. 3.8, 7.2)
}}

Rules:
- Pick the SINGLE best grade_level — the grade where this content fits best.
- grade_bands may include additional bands if the content is accessible to them.
- Keep "domain" specific enough that a teacher would recognize it as a topic.
- reading_level should reflect vocabulary, not the topic's theoretical grade.
"""


def _call_haiku(prompt: str) -> Optional[dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — cannot classify video")
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # Strip fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        # Find first { ... } block (Haiku sometimes trails with explanations)
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
        return None
    except Exception as e:
        log.warning("Haiku classify failed: %s", e)
        return None


def classify_video(video_id: str) -> dict:
    """Classify a video's transcript via Haiku. Merge-safe.

    Only writes fields that are currently NULL/empty. Existing values set by
    teachers (via PATCH /videos/{id}) are never overwritten.

    Returns:
        dict with the fields that were updated (or {} if no-op)
    """
    video = _fetch_video(video_id)
    if not video:
        return {"status": "video_not_found"}

    transcript = (video.get("transcript_text") or "").strip()
    if not transcript:
        return {"status": "no_transcript"}

    # Already fully classified? Skip.
    already_set = all([
        video.get("grade_level"),
        video.get("subject"),
        video.get("domain"),
        (video.get("grade_bands") and len(video["grade_bands"]) > 0),
        video.get("reading_level") is not None,
    ])
    if already_set:
        return {"status": "already_classified"}

    truncated = transcript[:CLASSIFY_MAX_CHARS]
    prompt = CLASSIFY_PROMPT.format(char_count=len(truncated), transcript=truncated)
    parsed = _call_haiku(prompt)
    if parsed is None:
        return {"status": "haiku_failed"}

    # Build UPDATE that only touches NULL fields (COALESCE preserves existing)
    updates: dict[str, Any] = {}
    if not video.get("grade_level") and parsed.get("grade_level"):
        updates["grade_level"] = str(parsed["grade_level"])
    if not video.get("subject") and parsed.get("subject"):
        updates["subject"] = str(parsed["subject"])
    if not video.get("domain") and parsed.get("domain"):
        updates["domain"] = str(parsed["domain"])[:255]
    existing_bands = video.get("grade_bands") or []
    if not existing_bands and parsed.get("grade_bands"):
        # Filter to known band values to avoid garbage from hallucination
        valid = {"K-2", "3-5", "6-8", "9-12", "college"}
        bands = [b for b in parsed["grade_bands"] if b in valid]
        if bands:
            updates["grade_bands"] = bands
    if video.get("reading_level") is None and parsed.get("reading_level") is not None:
        try:
            updates["reading_level"] = float(parsed["reading_level"])
        except (TypeError, ValueError):
            pass

    if not updates:
        return {"status": "nothing_to_update"}

    set_parts = ", ".join(f"{k} = %s" for k in updates)
    params = list(updates.values()) + [video_id]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE videos SET {set_parts} WHERE video_id = %s::uuid",
            params,
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    log.info("classify_video: video_id=%s updated=%s", video_id, list(updates.keys()))
    return {"status": "updated", "fields": updates}


# ---------------------------------------------------------------------------
# Phase 2c: Sync aligned standards → video_standards join table
# ---------------------------------------------------------------------------

def sync_video_standards(video_id: str, limit: int = SYNC_STANDARDS_LIMIT) -> dict:
    """Read the video's aligned chunks and upsert the top-N into video_standards.

    Relies on alignment having run on the video's knowledge_chunks rows (via
    scripts/align_standards_offline.py or the auto-alignment hook). Reads
    alignment_scores (jsonb array of {standard_id, code, strength}) across all
    chunks of this video, aggregates by standard_id, and picks the strongest
    N to write into video_standards.

    Idempotent: uses ON CONFLICT DO UPDATE so re-running updates strength if
    it has changed since last sync.

    Returns:
        dict with aligned_count + inserted_count
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Pull all alignment_scores entries from this video's chunks.
        # The knowledge_source for a video is named f"video_library — {video_id}"
        # (see index_video_transcript). We join through that to find chunks.
        cur.execute(
            """
            SELECT (a.value->>'standard_id')::uuid AS standard_id,
                   a.value->>'strength' AS strength
            FROM knowledge_chunks kc
            JOIN knowledge_sources ks ON ks.source_id = kc.source_id
            CROSS JOIN LATERAL jsonb_array_elements(COALESCE(kc.alignment_scores, '[]'::jsonb)) AS a
            WHERE ks.name = %s
              AND ks.upload_lane = 'video_library'
            """,
            (f"video_library — {video_id}",),
        )
        rows = cur.fetchall()
        if not rows:
            return {"status": "no_alignment_found", "aligned_count": 0}

        # Aggregate: prefer 'strong' over 'partial' per standard
        best: dict[str, str] = {}
        for r in rows:
            sid = str(r["standard_id"])
            strength = r["strength"] or "partial"
            if sid not in best or strength == "strong":
                best[sid] = strength

        # Sort strong first, limit
        sorted_items = sorted(
            best.items(),
            key=lambda kv: (0 if kv[1] == "strong" else 1),
        )[:limit]

        cur2 = conn.cursor()
        inserted = 0
        try:
            for sid, strength in sorted_items:
                cur2.execute(
                    """
                    INSERT INTO video_standards (video_id, standard_id, strength)
                    VALUES (%s::uuid, %s::uuid, %s)
                    ON CONFLICT (video_id, standard_id)
                    DO UPDATE SET strength = EXCLUDED.strength
                    """,
                    (video_id, sid, strength),
                )
                inserted += 1
            conn.commit()
        finally:
            cur2.close()

        log.info(
            "sync_video_standards: video_id=%s aligned_rows=%d unique_standards=%d synced=%d",
            video_id, len(rows), len(best), inserted,
        )
        return {
            "status": "synced",
            "aligned_count": len(rows),
            "unique_standards": len(best),
            "inserted_count": inserted,
        }
    finally:
        cur.close()
        conn.close()
