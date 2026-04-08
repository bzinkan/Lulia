"""Class Intelligence — per-class context accumulation for AI-aware generation.

Every class tab "grows smarter" over time. This module tracks standards covered,
vocabulary introduced, activity effectiveness, misconceptions, pacing, and builds
a natural-language AI context summary that gets injected into generation prompts.
"""
import json
import logging
from datetime import date, datetime

from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _today_iso() -> str:
    return date.today().isoformat()


def _ensure_row(cur, conn, class_id: str) -> None:
    """Lazy-init: insert the class_intelligence row if missing."""
    cur.execute(
        "SELECT 1 FROM class_intelligence WHERE class_id = %s::uuid",
        (class_id,),
    )
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO class_intelligence (class_id) VALUES (%s::uuid)",
            (class_id,),
        )
        conn.commit()
        log.info(f"[ClassIntel] Initialized intelligence row for class {class_id}")


def _fetch_row(cur, class_id: str) -> dict:
    """Fetch the full class_intelligence row as a dict."""
    cur.execute(
        "SELECT * FROM class_intelligence WHERE class_id = %s::uuid",
        (class_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else {}


def _fetch_class_info(cur, class_id: str) -> dict:
    """Fetch basic class metadata."""
    cur.execute(
        "SELECT name, subject, grade_level, period, school_year FROM classes WHERE class_id = %s::uuid",
        (class_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else {}


def _update_jsonb(cur, conn, class_id: str, column: str, value) -> None:
    """Write a JSONB column and bump last_updated."""
    cur.execute(
        f"UPDATE class_intelligence SET {column} = %s, last_updated = NOW() WHERE class_id = %s::uuid",
        (Json(value), class_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Core reads
# ---------------------------------------------------------------------------

def get_class_context(class_id: str) -> dict:
    """Fetch class_intelligence row + class info. Lazy-inits if needed."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        intel = _fetch_row(cur, class_id)
        class_info = _fetch_class_info(cur, class_id)
        intel["class_info"] = class_info
        return intel
    finally:
        cur.close()
        conn.close()


def get_ai_context_prompt(class_id: str) -> str:
    """Return the stored ai_context_summary, rebuilding if empty."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)
        summary = row.get("ai_context_summary", "")
        if not summary:
            cur.close()
            conn.close()
            rebuild_ai_context(class_id)
            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _fetch_row(cur, class_id)
            summary = row.get("ai_context_summary", "")
        return summary
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Standards tracking
# ---------------------------------------------------------------------------

def record_standard_covered(class_id: str, standard_code: str, date_covered: str = None) -> None:
    """Mark a standard as covered. Increments times_practiced if already present."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)

        covered = row.get("standards_covered") or []
        in_progress = row.get("standards_in_progress") or []
        d = date_covered or _today_iso()

        # Update or add
        found = False
        for s in covered:
            if s.get("code") == standard_code:
                s["times_practiced"] = s.get("times_practiced", 1) + 1
                found = True
                break

        if not found:
            covered.append({
                "code": standard_code,
                "date_introduced": d,
                "times_practiced": 1,
                "mastery_level": "introduced",
            })

        # Remove from in_progress if present
        in_progress = [s for s in in_progress if s.get("code") != standard_code]

        _update_jsonb(cur, conn, class_id, "standards_covered", covered)
        _update_jsonb(cur, conn, class_id, "standards_in_progress", in_progress)
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


def record_standard_started(class_id: str, standard_code: str) -> None:
    """Mark a standard as in-progress (unless already covered)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)

        covered = row.get("standards_covered") or []
        in_progress = row.get("standards_in_progress") or []

        # Skip if already covered
        if any(s.get("code") == standard_code for s in covered):
            return

        # Skip if already in progress
        if any(s.get("code") == standard_code for s in in_progress):
            return

        in_progress.append({
            "code": standard_code,
            "date_started": _today_iso(),
        })
        _update_jsonb(cur, conn, class_id, "standards_in_progress", in_progress)
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


# ---------------------------------------------------------------------------
# Vocabulary & concepts
# ---------------------------------------------------------------------------

def add_vocabulary(class_id: str, terms: list[dict]) -> None:
    """Add vocabulary terms. Each dict: {term, definition, subject_area}. Deduplicates by term."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)
        existing = row.get("vocabulary_introduced") or []
        existing_names = {v.get("term", "").lower() for v in existing}

        for t in terms:
            if t.get("term", "").lower() not in existing_names:
                existing.append({
                    "term": t.get("term", ""),
                    "definition": t.get("definition", ""),
                    "subject_area": t.get("subject_area", ""),
                    "date_introduced": _today_iso(),
                })
                existing_names.add(t.get("term", "").lower())

        _update_jsonb(cur, conn, class_id, "vocabulary_introduced", existing)
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


def add_concept(class_id: str, concept: str, related_standards: list[str] = None) -> None:
    """Add a key concept. Deduplicates by concept name."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)
        concepts = row.get("key_concepts") or []

        if any(c.get("concept", "").lower() == concept.lower() for c in concepts):
            return

        concepts.append({
            "concept": concept,
            "date_introduced": _today_iso(),
            "related_standards": related_standards or [],
        })
        _update_jsonb(cur, conn, class_id, "key_concepts", concepts)
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


# ---------------------------------------------------------------------------
# Activity ratings
# ---------------------------------------------------------------------------

def rate_activity(class_id: str, activity_id: str, activity_type: str,
                  topic: str, rating: int, notes: str = "") -> None:
    """Rate an activity 1-5 and recalculate preferred types."""
    rating = max(1, min(5, rating))
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)
        ratings = row.get("activity_ratings") or []

        ratings.append({
            "activity_id": activity_id,
            "type": activity_type,
            "topic": topic,
            "rating": rating,
            "notes": notes,
            "date": _today_iso(),
        })
        _update_jsonb(cur, conn, class_id, "activity_ratings", ratings)

        # Recalculate preferred_activity_types
        type_totals: dict[str, list[int]] = {}
        for r in ratings:
            t = r.get("type", "unknown")
            type_totals.setdefault(t, []).append(r.get("rating", 3))

        ranked = sorted(
            type_totals.keys(),
            key=lambda t: sum(type_totals[t]) / len(type_totals[t]),
            reverse=True,
        )
        _update_jsonb(cur, conn, class_id, "preferred_activity_types", ranked)
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


# ---------------------------------------------------------------------------
# Misconceptions & class profile
# ---------------------------------------------------------------------------

def note_misconception(class_id: str, topic: str, misconception: str,
                       correction: str = "") -> None:
    """Record a common misconception observed in class."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)
        items = row.get("common_misconceptions") or []
        items.append({
            "topic": topic,
            "misconception": misconception,
            "correction": correction,
            "date_noted": _today_iso(),
        })
        _update_jsonb(cur, conn, class_id, "common_misconceptions", items)
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


def update_class_profile(class_id: str, strengths: list[str] = None,
                         challenges: list[str] = None) -> None:
    """Update class strengths and/or challenges."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        if strengths is not None:
            _update_jsonb(cur, conn, class_id, "class_strengths", strengths)
        if challenges is not None:
            _update_jsonb(cur, conn, class_id, "class_challenges", challenges)
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


# ---------------------------------------------------------------------------
# Pacing
# ---------------------------------------------------------------------------

def update_pacing(class_id: str, status: str, current_unit: str = "",
                  notes: str = "") -> None:
    """Update pacing status (ahead / on_track / behind)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        cur.execute(
            """UPDATE class_intelligence
               SET pacing_status = %s, current_unit = %s, pacing_notes = %s, last_updated = NOW()
               WHERE class_id = %s::uuid""",
            (status, current_unit, notes, class_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


def complete_unit(class_id: str, unit_name: str) -> None:
    """Mark a unit as completed."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)
        units = row.get("units_completed") or []
        units.append({
            "unit_name": unit_name,
            "date_completed": _today_iso(),
        })
        _update_jsonb(cur, conn, class_id, "units_completed", units)
    finally:
        cur.close()
        conn.close()

    rebuild_ai_context(class_id)


# ---------------------------------------------------------------------------
# AI Context Summary Builder
# ---------------------------------------------------------------------------

def rebuild_ai_context(class_id: str) -> str:
    """Rebuild the natural language ai_context_summary from all intelligence data."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        _ensure_row(cur, conn, class_id)
        row = _fetch_row(cur, class_id)
        info = _fetch_class_info(cur, class_id)

        parts = []

        # Class header
        name = info.get("name", "Unknown Class")
        subject = info.get("subject", "")
        grade = info.get("grade_level", "")
        period = info.get("period", "")
        header = f"Class: {name}"
        if grade and subject:
            header = f"Class: {grade} {subject}"
        if period:
            header += f" (Period {period})"
        parts.append(header)

        # Standards covered
        covered = row.get("standards_covered") or []
        if covered:
            codes = []
            for s in covered:
                c = s.get("code", "")
                tp = s.get("times_practiced", 1)
                codes.append(f"{c} ({tp}x practiced)" if tp > 1 else c)
            parts.append(f"Standards covered this year: {', '.join(codes)}")

        # Standards in progress
        in_prog = row.get("standards_in_progress") or []
        if in_prog:
            codes = [s.get("code", "") for s in in_prog]
            parts.append(f"Currently teaching: {', '.join(codes)}")

        # Vocabulary
        vocab = row.get("vocabulary_introduced") or []
        if vocab:
            terms = [v.get("term", "") for v in vocab]
            if len(terms) > 15:
                terms_str = ", ".join(terms[:15]) + f" (+{len(terms) - 15} more)"
            else:
                terms_str = ", ".join(terms)
            parts.append(f"Vocabulary already introduced: {terms_str}")

        # Key concepts
        concepts = row.get("key_concepts") or []
        if concepts:
            cnames = [c.get("concept", "") for c in concepts]
            parts.append(f"Key concepts covered: {', '.join(cnames)}")

        # Class strengths
        strengths = row.get("class_strengths") or []
        if strengths:
            parts.append(f"Class strengths: {', '.join(strengths)}")

        # Class challenges
        challenges = row.get("class_challenges") or []
        if challenges:
            parts.append(f"Class challenges: {', '.join(challenges)}")

        # Preferred activities
        prefs = row.get("preferred_activity_types") or []
        if prefs:
            parts.append(f"Preferred activities (by effectiveness): {', '.join(prefs)}")

        # Misconceptions
        miscon = row.get("common_misconceptions") or []
        if miscon:
            items = []
            for m in miscon[-5:]:  # Last 5
                items.append(f"{m.get('misconception', '')}")
            parts.append(f"Common misconceptions: {'; '.join(items)}")

        # Pacing
        status = row.get("pacing_status", "on_track")
        current = row.get("current_unit", "")
        units_done = row.get("units_completed") or []
        pacing_str = f"Pacing: {status.replace('_', ' ').title()}"
        if units_done:
            pacing_str += f" -- {len(units_done)} unit(s) completed"
        if current:
            pacing_str += f", currently on: {current}"
        parts.append(pacing_str)

        summary = "\n".join(parts)

        # Store it back
        cur.execute(
            """UPDATE class_intelligence
               SET ai_context_summary = %s, last_updated = NOW()
               WHERE class_id = %s::uuid""",
            (summary, class_id),
        )
        conn.commit()
        log.info(f"[ClassIntel] Rebuilt AI context for class {class_id}")
        return summary
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Auto-extraction from assignments
# ---------------------------------------------------------------------------

def auto_extract_from_assignment(class_id: str, assignment_id: str) -> None:
    """Extract intelligence from a stored assignment (standards, vocabulary).

    Called after assignment creation. Non-fatal — logs warnings on failure.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT standards_ids, questions, title FROM assignments WHERE assignment_id = %s",
            (assignment_id,),
        )
        row = cur.fetchone()
        if not row:
            log.warning(f"[ClassIntel] Assignment {assignment_id} not found for extraction")
            return

        # Record standards
        standards = row.get("standards_ids") or []
        for code in standards:
            if isinstance(code, str) and code.strip():
                try:
                    record_standard_covered(class_id, code.strip())
                except Exception as e:
                    log.warning(f"[ClassIntel] Failed to record standard {code}: {e}")

        # Extract vocabulary from question text
        questions = row.get("questions") or []
        terms = _extract_vocab_from_questions(questions)
        if terms:
            try:
                add_vocabulary(class_id, terms)
            except Exception as e:
                log.warning(f"[ClassIntel] Failed to add vocabulary: {e}")

        log.info(f"[ClassIntel] Auto-extracted from assignment {assignment_id}: "
                 f"{len(standards)} standards, {len(terms)} vocab terms")
    except Exception as e:
        log.warning(f"[ClassIntel] Auto-extraction failed for assignment {assignment_id}: {e}")
    finally:
        cur.close()
        conn.close()


def _extract_vocab_from_questions(questions: list) -> list[dict]:
    """Simple keyword extraction — pulls bolded/quoted terms from question text."""
    terms = []
    seen = set()

    for q in questions:
        text = ""
        if isinstance(q, dict):
            text = q.get("question", "") + " " + q.get("stem", "") + " " + q.get("text", "")
        elif isinstance(q, str):
            text = q

        # Extract **bolded** terms
        import re
        for match in re.finditer(r'\*\*([^*]+)\*\*', text):
            term = match.group(1).strip()
            if term.lower() not in seen and len(term) < 80:
                terms.append({"term": term, "definition": "", "subject_area": ""})
                seen.add(term.lower())

        # Extract "quoted" terms
        for match in re.finditer(r'"([^"]+)"', text):
            term = match.group(1).strip()
            if term.lower() not in seen and 2 < len(term) < 80:
                terms.append({"term": term, "definition": "", "subject_area": ""})
                seen.add(term.lower())

    return terms


# ---------------------------------------------------------------------------
# Auto-extraction from lesson plans
# ---------------------------------------------------------------------------

def auto_extract_from_lesson_plan(class_id: str, lesson_plan_data: dict) -> None:
    """Extract standards, vocabulary, and concepts from a lesson plan dict.

    Expected keys: standards (list), vocabulary (list of dicts or strings),
    objectives (list), topic (str).
    """
    try:
        # Standards
        standards = lesson_plan_data.get("standards") or lesson_plan_data.get("standards_ids") or []
        for code in standards:
            if isinstance(code, str) and code.strip():
                try:
                    record_standard_covered(class_id, code.strip())
                except Exception as e:
                    log.warning(f"[ClassIntel] Failed to record standard from lesson plan: {e}")

        # Vocabulary
        vocab_raw = lesson_plan_data.get("vocabulary") or []
        terms = []
        for v in vocab_raw:
            if isinstance(v, dict):
                terms.append({
                    "term": v.get("term", v.get("word", "")),
                    "definition": v.get("definition", ""),
                    "subject_area": v.get("subject_area", ""),
                })
            elif isinstance(v, str):
                terms.append({"term": v, "definition": "", "subject_area": ""})
        if terms:
            add_vocabulary(class_id, terms)

        # Concepts from objectives/topic
        topic = lesson_plan_data.get("topic", "")
        if topic:
            add_concept(class_id, topic, related_standards=[str(s) for s in standards])

        objectives = lesson_plan_data.get("objectives") or []
        for obj in objectives:
            if isinstance(obj, str) and len(obj) > 5:
                add_concept(class_id, obj, related_standards=[str(s) for s in standards])

        log.info(f"[ClassIntel] Auto-extracted from lesson plan for class {class_id}")
    except Exception as e:
        log.warning(f"[ClassIntel] Lesson plan extraction failed for class {class_id}: {e}")
