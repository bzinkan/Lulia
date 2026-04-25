"""
Reference Retrieval — finds reference exemplars by structural shape.

The Pedagogy Director uses this module to retrieve REAL worksheets, slide
decks, lesson plans, etc. from the teacher_archive and teacher_reference
lanes that match the shape of what the teacher is asking for. The Content
Agent then uses these exemplars as structural templates — it generates new
content that matches the shape of a real reference, not something
LLM-hallucinated from general training data.

This is the core of reference-grounded generation. Without it, the
pedagogy packs constrain style but not shape, so outputs can still drift
toward generic LLM slop. With it, the generated output starts from "here's
what a real 6th grade rock cycle worksheet actually looks like, now make
something in the same shape with fresh content."

Retrieval strategy:
  1. Build semantic query embedding from topic + standards description
  2. Query knowledge_chunks JOIN knowledge_sources with:
     - grade_bands filter (match target band)
     - upload_lane priority (teacher_archive > teacher_reference > others)
     - artifact_type filter (if caller specifies: worksheet, slide_deck, etc.)
     - reference_metadata IS NOT NULL (only analyzed chunks)
  3. Rank by a blended score: semantic distance + structural match bonus
  4. Deduplicate by source_id (one exemplar per document)
  5. Return top K with full metadata

Callers can filter strictly (only worksheets) or loosely (any artifact),
and can prefer teacher lanes heavily or allow system OER to bubble up.
"""
import logging
from typing import Optional

from psycopg2.extras import RealDictCursor

from src.lms_agents.tools.bedrock_embedding import embed_text
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


# Default lane priority — teacher sources first, then K-8 reference,
# then system OER textbooks as a fallback. OpenStax is last because
# it's textbook prose, not teacher-ready artifacts.
DEFAULT_LANE_PRIORITY = [
    "teacher_archive",     # Brian's own teaching materials
    "teacher_reference",   # K-8 free reference library
    "loc",                 # Library of Congress primary sources
    "oer_textbook",        # Legacy/imported OER
    "openstax",            # Textbook chapters (reference_text only)
]

# Lanes a K-2 expert should NEVER pull from — too academic, wrong register
K2_EXCLUDED_LANES = ["openstax"]
# 3-5 also avoids full textbook prose
G35_EXCLUDED_LANES = ["openstax"]


def _band_for_grade(grade: str) -> str:
    g = str(grade).strip().upper()
    if g in ("K", "KINDERGARTEN", "0", "1", "2"):
        return "K-2"
    if g in ("3", "4", "5"):
        return "3-5"
    if g in ("6", "7", "8"):
        return "6-8"
    return "9-12"


def _excluded_lanes_for_band(band: str) -> list[str]:
    if band == "K-2":
        return K2_EXCLUDED_LANES
    if band == "3-5":
        return G35_EXCLUDED_LANES
    return []


def find_reference_exemplars(
    topic_query: str,
    grade: str,
    subject: str | None = None,
    artifact_type: str | None = None,
    required_structural_features: list[str] | None = None,
    lanes: list[str] | None = None,
    teacher_id: str | None = None,
    top_k: int = 3,
    deduplicate_by_source: bool = True,
    include_excerpt: bool = True,
    excerpt_max_chars: int = 600,
) -> list[dict]:
    """
    Retrieve reference exemplars matching the requested shape.

    Args:
        topic_query: semantic search text (e.g. "rock cycle weathering erosion"
                     or the standard description).
        grade: specific grade ('K', '1', '7', '11', etc.) — determines grade_band.
        subject: optional subject filter ('Science', 'Math', etc.).
        artifact_type: optional hint — 'worksheet', 'slide_deck', 'lesson_plan',
                       'assessment', 'reading_passage', etc. If None, any shape.
        required_structural_features: list of structural_features tags that
                       MUST all be present on the chunk's metadata.
        lanes: ordered list of upload_lanes to prefer. Defaults to
               DEFAULT_LANE_PRIORITY minus excluded lanes for the grade band.
        teacher_id: optional — scopes teacher_archive retrieval to this teacher.
        top_k: number of exemplars to return.
        deduplicate_by_source: if True, only one chunk per source_id (so you
                               get K distinct reference documents).
        include_excerpt: if True, populate 'excerpt' with a short content preview.
        excerpt_max_chars: how much content to include in the excerpt.

    Returns:
        List of exemplar dicts with keys:
          source_id, source_name, upload_lane, file_type, grade_level, subject,
          artifact_type, visual_density, structural_features, scaffolding_features,
          content_shape_description, question_count_estimate, relevance_score,
          excerpt (if include_excerpt=True).

        Empty list if no matches found or embedding fails.
    """
    query_embedding = embed_text(topic_query)
    if query_embedding is None:
        log.warning("[RefRetrieval] query embedding failed — returning empty")
        return []
    embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

    band = _band_for_grade(grade)

    if lanes is None:
        excluded = set(_excluded_lanes_for_band(band))
        lanes = [l for l in DEFAULT_LANE_PRIORITY if l not in excluded]

    # Build the WHERE clause
    conditions = [
        "ks.processing_status = 'complete'",
        "kc.embedding IS NOT NULL",
        "kc.reference_metadata IS NOT NULL",
        # Grade band must match (either exactly or via overlap)
        "%s = ANY(kc.grade_bands)",
    ]
    params: list = [band]

    # Lane filter
    if lanes:
        lane_placeholders = ",".join(["%s"] * len(lanes))
        conditions.append(f"ks.upload_lane IN ({lane_placeholders})")
        params.extend(lanes)

    # Subject filter (loose match)
    if subject:
        conditions.append("(ks.subject ILIKE %s OR ks.subject IS NULL)")
        params.append(f"%{subject}%")

    # Teacher scope: if requesting teacher_archive lane, scope to this teacher
    if teacher_id and "teacher_archive" in (lanes or []):
        conditions.append(
            "(ks.upload_lane != 'teacher_archive' OR ks.teacher_id = %s::uuid)"
        )
        params.append(teacher_id)

    # Artifact type filter (JSONB extract)
    if artifact_type:
        conditions.append("kc.reference_metadata->>'artifact_type' = %s")
        params.append(artifact_type)

    # Required structural features — all must be present in the JSONB array
    if required_structural_features:
        for feat in required_structural_features:
            conditions.append("kc.reference_metadata->'structural_features' ? %s")
            params.append(feat)

    where = " AND ".join(conditions)

    # Semantic similarity ranking. We retrieve more candidates than top_k
    # so deduplication by source has room to work.
    candidate_limit = top_k * 5 if deduplicate_by_source else top_k

    sql = f"""
        SELECT kc.chunk_id, kc.content, kc.section_heading, kc.chunk_number,
               kc.reference_metadata, kc.grade_bands,
               ks.source_id, ks.name AS source_name, ks.upload_lane,
               ks.file_type, ks.subject, ks.grade_level,
               kc.embedding <=> %s::vector AS distance
        FROM knowledge_chunks kc
        JOIN knowledge_sources ks ON kc.source_id = ks.source_id
        WHERE {where}
        ORDER BY kc.embedding <=> %s::vector ASC
        LIMIT %s
    """
    all_params = [embedding_str] + params + [embedding_str, candidate_limit]

    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # See rag_search.search_kb for why the vector scan gets a hard cap.
        # Reference retrieval adds JSONB filters on reference_metadata, which
        # the planner occasionally gets creative with — a 5s wall keeps a
        # bad plan from stalling an assignment generate.
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute(sql, all_params)
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    # Deduplicate by source_id — keep the first (best-ranked) chunk per source
    seen_sources: set[str] = set()
    exemplars: list[dict] = []
    for row in rows:
        sid = str(row["source_id"])
        if deduplicate_by_source and sid in seen_sources:
            continue
        seen_sources.add(sid)

        meta = row.get("reference_metadata") or {}
        exemplar = {
            "source_id": sid,
            "source_name": row.get("source_name") or "",
            "upload_lane": row.get("upload_lane") or "",
            "file_type": row.get("file_type") or "",
            "grade_level": row.get("grade_level") or "",
            "subject": row.get("subject") or "",
            "artifact_type": meta.get("artifact_type"),
            "visual_density": meta.get("visual_density"),
            "structural_features": meta.get("structural_features") or [],
            "scaffolding_features": meta.get("scaffolding_features") or [],
            "content_shape_description": meta.get("content_shape_description") or "",
            "question_count_estimate": meta.get("question_count_estimate"),
            "relevance_score": 1.0 - float(row.get("distance") or 1.0),
        }
        if include_excerpt:
            content = (row.get("content") or "")[:excerpt_max_chars]
            exemplar["excerpt"] = content

        exemplars.append(exemplar)
        if len(exemplars) >= top_k:
            break

    return exemplars


def format_exemplars_for_prompt(exemplars: list[dict]) -> str:
    """
    Render exemplars as a compact block for injection into Content Agent
    or Pedagogy Director prompts. Emphasizes structural shape over raw text.
    """
    if not exemplars:
        return ""

    lines = ["=== REFERENCE EXEMPLARS (match these structural shapes) ===\n"]
    for i, ex in enumerate(exemplars, 1):
        lines.append(f"--- Exemplar {i}: {ex.get('source_name', 'unknown')[:80]} ---")
        lines.append(f"  Lane:         {ex.get('upload_lane')} ({ex.get('file_type')})")
        lines.append(f"  Artifact:     {ex.get('artifact_type')}")
        lines.append(f"  Visual:       {ex.get('visual_density')} density")
        if ex.get('question_count_estimate') is not None:
            lines.append(f"  Questions:    ~{ex['question_count_estimate']}")
        if ex.get('structural_features'):
            lines.append(f"  Structure:    {', '.join(ex['structural_features'])}")
        if ex.get('scaffolding_features'):
            lines.append(f"  Scaffolds:    {', '.join(ex['scaffolding_features'])}")
        if ex.get('content_shape_description'):
            lines.append(f"  Shape:        {ex['content_shape_description']}")
        if ex.get('excerpt'):
            lines.append(f"  Excerpt:")
            for line in ex['excerpt'].split("\n")[:6]:
                lines.append(f"    | {line[:120]}")
        lines.append("")

    lines.append("INSTRUCTIONS FOR USING THESE EXEMPLARS:")
    lines.append("- Match the STRUCTURAL SHAPE of the closest exemplar (layout, ")
    lines.append("  question count, feature mix, scaffold pattern).")
    lines.append("- Do NOT copy content verbatim — generate FRESH content in")
    lines.append("  the same shape.")
    lines.append("- If multiple exemplars differ, prefer the one from the highest-")
    lines.append("  priority lane (teacher_archive > teacher_reference > others).")
    lines.append("=== END REFERENCE EXEMPLARS ===")
    return "\n".join(lines)
