"""
Reference Analyzer — classifies a knowledge source into structural metadata.

Given a knowledge source (worksheet, slide deck, lesson plan, etc.), this
module calls Claude Haiku once per source to extract its artifact type,
visual density, structural features, scaffolding features, and a short
content-shape description. The result is written to `reference_metadata`
on every chunk of that source so the Pedagogy Director can retrieve
reference exemplars by structural shape — not just semantic similarity.

Usage:
    from src.lms_agents.tools.reference_analyzer import (
        analyze_source,
        analyze_all_teacher_sources,
    )

    # Analyze a single source
    meta = analyze_source(source_id)

    # Backfill all unanalyzed teacher-lane sources
    stats = analyze_all_teacher_sources(limit=None)
"""
import json
import logging
import os
import re
import time
from typing import Optional

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

HAIKU = "claude-haiku-4-5-20251001"

# How many representative chunks to send per source (first N by chunk_number)
CHUNKS_PER_ANALYSIS = 3
# Max chars per chunk we send to the LLM (trim very long chunks)
MAX_CHUNK_CHARS = 1200


# ---------------------------------------------------------------------------
# Canonical metadata vocabulary (used in the prompt as a closed set)
# ---------------------------------------------------------------------------

ARTIFACT_TYPES = [
    "worksheet",
    "slide_deck",
    "lesson_plan",
    "assessment",
    "reading_passage",
    "activity",
    "lab_report",
    "game",
    "anchor_chart",
    "rubric",
    "reference_text",      # textbook chapters, reference prose
    "graphic_organizer",
    "task_cards",
    # Video library artifact types (classifies transcripts)
    "instructional_video",   # direct-teach, "here's how fractions work"
    "demonstration",         # hands-on / experiment / model-it
    "read_aloud",            # story reading, poem, text performance
    "virtual_field_trip",    # museum tour, ecosystem walk, historical site
    "song_or_chant",         # mnemonic, rhyme, educational song
    "other",
]

VISUAL_DENSITIES = ["none", "low", "medium", "high"]

STRUCTURAL_FEATURES = [
    "multiple_choice",
    "fill_in_blank",
    "short_answer",
    "extended_response",
    "word_problem",
    "computation_problem",
    "diagram",
    "data_table",
    "chart_or_graph",
    "image_or_photo",
    "numbered_steps",
    "bulleted_list",
    "vocabulary_box",
    "definitions",
    "heading_structure",
    "examples_worked_out",
    "directions_block",
    "open_ended_prompt",
    "reading_comprehension_questions",
    "lab_procedure",
    "timeline",
    "sequence_of_events",
]

SCAFFOLDING_FEATURES = [
    "word_bank",
    "sentence_starters",
    "worked_example",
    "hint_box",
    "answer_key",
    "rubric_visible",
    "success_criteria",
    "color_coded_steps",
    "visual_anchor",
    "manipulative_reference",
    "graphic_organizer_scaffold",
    "frame_or_template",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _extract_json(text: str) -> Optional[dict]:
    """Pull a JSON object out of a possibly-fenced LLM response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def _fetch_source_sample(source_id: str) -> Optional[dict]:
    """Load the source row + first N chunks for analysis."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """SELECT source_id, name, subject, grade_level, upload_lane,
                      file_type, original_path
               FROM knowledge_sources
               WHERE source_id = %s""",
            (source_id,),
        )
        source = cur.fetchone()
        if not source:
            return None

        cur.execute(
            """SELECT chunk_id, chunk_number, content, page_number, section_heading
               FROM knowledge_chunks
               WHERE source_id = %s
               ORDER BY chunk_number ASC
               LIMIT %s""",
            (source_id, CHUNKS_PER_ANALYSIS),
        )
        chunks = cur.fetchall() or []
        return {"source": dict(source), "chunks": [dict(c) for c in chunks]}
    finally:
        cur.close()
        conn.close()


def _build_prompt(source: dict, chunks: list[dict]) -> tuple[str, str]:
    """Build system + user prompts for the analysis call."""
    system = (
        "You are a content structural analyst for an educational LMS. Your job "
        "is to look at a source document (worksheet, slide deck, lesson plan, "
        "textbook chapter, etc.) and classify its STRUCTURAL SHAPE — what kind "
        "of artifact it is, what pedagogical features it has, how much visual "
        "content it contains — so that other AI agents can use it as a "
        "REFERENCE EXEMPLAR when generating new materials in the same shape. "
        "You do NOT evaluate content quality or factual accuracy. You only "
        "classify structure. Be decisive and pick from the provided vocabularies."
    )

    chunk_samples = []
    for c in chunks:
        text = (c.get("content") or "")[:MAX_CHUNK_CHARS]
        heading = c.get("section_heading") or ""
        chunk_samples.append(
            f"--- Chunk {c.get('chunk_number', '?')}"
            + (f" (section: {heading})" if heading else "")
            + f" ---\n{text}"
        )
    samples_block = "\n\n".join(chunk_samples) if chunk_samples else "(no chunks)"

    user = f"""Analyze this source document and classify its STRUCTURAL SHAPE.

SOURCE METADATA:
- Name: {source.get('name', '')}
- Subject: {source.get('subject') or '(unknown)'}
- Grade level: {source.get('grade_level') or '(unknown)'}
- File type: {source.get('file_type', '')}
- Upload lane: {source.get('upload_lane', '')}

CONTENT SAMPLES (first {CHUNKS_PER_ANALYSIS} chunks):
{samples_block}

Return a single JSON object with EXACTLY these fields:

{{
  "artifact_type": "<one of: {' | '.join(ARTIFACT_TYPES)}>",
  "visual_density": "<one of: {' | '.join(VISUAL_DENSITIES)}>",
  "structural_features": ["<pick from: {', '.join(STRUCTURAL_FEATURES)}>"],
  "scaffolding_features": ["<pick from: {', '.join(SCAFFOLDING_FEATURES)}>"],
  "question_count_estimate": <int or null>,
  "has_standards_alignment_cues": <true/false>,
  "content_shape_description": "<one short sentence describing the artifact's shape, not its content>",
  "confidence": <float 0.0-1.0>
}}

Rules:
- Pick ONE artifact_type from the list. If nothing fits, use "other".
- Only use feature tags from the provided vocabularies.
- content_shape_description should describe the SHAPE not the TOPIC.
  Good: "10-question multiple-choice assessment with vocabulary box"
  Bad:  "A quiz about the rock cycle"
- Respond with ONLY the JSON object, no prose.
"""
    return system, user


# ---------------------------------------------------------------------------
# Public analysis functions
# ---------------------------------------------------------------------------

def analyze_source(
    source_id: str,
    client: Optional[anthropic.Anthropic] = None,
    write_to_chunks: bool = True,
) -> Optional[dict]:
    """
    Analyze one source via Haiku and (optionally) write the result to all
    chunks of that source. Returns the parsed metadata dict, or None on
    failure.
    """
    sample = _fetch_source_sample(source_id)
    if not sample or not sample["chunks"]:
        return None

    if client is None:
        client = _get_client()

    system, user = _build_prompt(sample["source"], sample["chunks"])

    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text
    except Exception as e:
        log.warning(f"[RefAnalyzer] Haiku call failed for source {source_id}: {e}")
        return None

    meta = _extract_json(text)
    if not meta:
        log.warning(f"[RefAnalyzer] Could not parse JSON for source {source_id}")
        return None

    # Normalize + validate the metadata
    meta = _normalize_metadata(meta)
    meta["_source_id"] = str(source_id)
    meta["_analyzer_version"] = "v1"
    meta["_analyzed_at_unix"] = int(time.time())

    if write_to_chunks:
        _write_metadata_to_chunks(source_id, meta)

    return meta


def _normalize_metadata(meta: dict) -> dict:
    """Coerce LLM output into our canonical vocabulary + safe defaults."""
    out: dict = {}

    # artifact_type — must be in the canonical list
    at = (meta.get("artifact_type") or "other").strip().lower()
    out["artifact_type"] = at if at in ARTIFACT_TYPES else "other"

    # visual_density
    vd = (meta.get("visual_density") or "low").strip().lower()
    out["visual_density"] = vd if vd in VISUAL_DENSITIES else "low"

    # structural_features — filter to canonical list, dedupe
    sf = meta.get("structural_features") or []
    if isinstance(sf, list):
        out["structural_features"] = sorted(
            {s.strip().lower() for s in sf if isinstance(s, str) and s.strip().lower() in STRUCTURAL_FEATURES}
        )
    else:
        out["structural_features"] = []

    # scaffolding_features
    scf = meta.get("scaffolding_features") or []
    if isinstance(scf, list):
        out["scaffolding_features"] = sorted(
            {s.strip().lower() for s in scf if isinstance(s, str) and s.strip().lower() in SCAFFOLDING_FEATURES}
        )
    else:
        out["scaffolding_features"] = []

    # question_count_estimate
    qc = meta.get("question_count_estimate")
    try:
        out["question_count_estimate"] = int(qc) if qc is not None else None
    except (TypeError, ValueError):
        out["question_count_estimate"] = None

    # has_standards_alignment_cues
    out["has_standards_alignment_cues"] = bool(meta.get("has_standards_alignment_cues", False))

    # content_shape_description
    desc = meta.get("content_shape_description") or ""
    if isinstance(desc, str):
        out["content_shape_description"] = desc[:300].strip()
    else:
        out["content_shape_description"] = ""

    # confidence
    conf = meta.get("confidence", 0.5)
    try:
        c = float(conf)
        out["confidence"] = max(0.0, min(1.0, c))
    except (TypeError, ValueError):
        out["confidence"] = 0.5

    return out


def _write_metadata_to_chunks(source_id: str, meta: dict) -> int:
    """Copy the same reference_metadata onto every chunk of a source."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE knowledge_chunks
               SET reference_metadata = %s
               WHERE source_id = %s""",
            (Json(meta), source_id),
        )
        count = cur.rowcount
        conn.commit()
        return count
    except Exception as e:
        conn.rollback()
        log.error(f"[RefAnalyzer] DB write failed for {source_id}: {e}")
        return 0
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Bulk backfill
# ---------------------------------------------------------------------------

def bulk_set_openstax_metadata() -> int:
    """
    OpenStax content is always textbook prose — set artifact_type=reference_text
    deterministically without burning API calls on ~40K chunks.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        meta = {
            "artifact_type": "reference_text",
            "visual_density": "low",
            "structural_features": ["heading_structure", "examples_worked_out"],
            "scaffolding_features": [],
            "question_count_estimate": None,
            "has_standards_alignment_cues": False,
            "content_shape_description": "Textbook prose with headings and worked examples",
            "confidence": 0.95,
            "_analyzer_version": "v1-bulk",
        }
        cur.execute(
            """UPDATE knowledge_chunks
               SET reference_metadata = %s
               WHERE source_id IN (
                   SELECT source_id FROM knowledge_sources
                   WHERE upload_lane = 'openstax'
               )
               AND reference_metadata IS NULL""",
            (Json(meta),),
        )
        count = cur.rowcount
        conn.commit()
        return count
    finally:
        cur.close()
        conn.close()


def list_unanalyzed_sources(
    lanes: list[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    """Return source_ids that have no analyzed chunks in the target lanes."""
    if lanes is None:
        lanes = ["teacher_archive", "teacher_reference", "loc"]

    conn = get_connection()
    cur = conn.cursor()
    try:
        lane_placeholders = ",".join(["%s"] * len(lanes))
        query = f"""
            SELECT DISTINCT s.source_id
            FROM knowledge_sources s
            WHERE s.upload_lane IN ({lane_placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM knowledge_chunks c
                  WHERE c.source_id = s.source_id
                    AND c.reference_metadata IS NOT NULL
              )
        """
        params: list = list(lanes)
        if limit:
            query += " LIMIT %s"
            params.append(limit)
        cur.execute(query, params)
        return [str(row[0]) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def analyze_all_teacher_sources(
    lanes: list[str] | None = None,
    limit: int | None = None,
    progress_every: int = 25,
) -> dict:
    """
    Backfill reference_metadata for all unanalyzed sources in target lanes.

    Returns {'analyzed': N, 'failed': N, 'skipped': N, 'chunks_updated': N}.
    """
    source_ids = list_unanalyzed_sources(lanes=lanes, limit=limit)
    log.info(f"[RefAnalyzer] {len(source_ids)} sources to analyze")

    client = _get_client()
    stats = {"analyzed": 0, "failed": 0, "chunks_updated": 0}

    for i, source_id in enumerate(source_ids, 1):
        meta = analyze_source(source_id, client=client, write_to_chunks=True)
        if meta:
            stats["analyzed"] += 1
            # Count chunks updated for this source
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM knowledge_chunks WHERE source_id = %s",
                (source_id,),
            )
            stats["chunks_updated"] += cur.fetchone()[0] or 0
            cur.close()
            conn.close()
        else:
            stats["failed"] += 1

        if i % progress_every == 0:
            log.info(
                f"[RefAnalyzer] progress: {i}/{len(source_ids)} "
                f"({stats['analyzed']} ok, {stats['failed']} failed)"
            )

    return stats
