"""
Curriculum Generator — builds a scope & sequence from state standards.

For teachers who don't have a pacing guide, this generates a curriculum
using the state standards already loaded in the database (1.21M standards
across 51 frameworks). Claude Sonnet groups standards into logical units
with an intended teaching sequence and estimated weeks per unit.

The teacher can generate:
  - "full_year" — complete 36-week scope & sequence, all units at once
  - "next_unit" — just the next unit based on what they've already covered

The generated curriculum is stored in curriculum_calendar with
generation_source='ai_generated' and behaves exactly like an uploaded
pacing guide from that point on.
"""
import json
import logging
import os
import re
from uuid import uuid4

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

SONNET = "claude-sonnet-4-20250514"


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _fetch_state_standards(
    state_code: str,
    grade_level: str,
    subject: str,
    limit: int = 500,
) -> list[dict]:
    """
    Query the standards table for all standards matching the given
    state framework, grade level, and subject.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """SELECT s.code, s.description, s.grade_level, s.subject,
                      s.domain, s.cluster, f.name AS framework_name
               FROM standards s
               JOIN standards_frameworks f ON s.framework_id = f.framework_id
               WHERE f.is_active = true
                 AND f.state_code = %s
                 AND s.grade_level = %s
                 AND s.subject ILIKE %s
               ORDER BY s.domain, s.code
               LIMIT %s""",
            (state_code, grade_level, f"%{subject}%", limit),
        )
        rows = [dict(r) for r in cur.fetchall()]

        # If no state-specific results, fall back to Common Core
        if not rows:
            cur.execute(
                """SELECT s.code, s.description, s.grade_level, s.subject,
                          s.domain, s.cluster, f.name AS framework_name
                   FROM standards s
                   JOIN standards_frameworks f ON s.framework_id = f.framework_id
                   WHERE f.is_active = true
                     AND f.tier = 'national'
                     AND s.grade_level = %s
                     AND s.subject ILIKE %s
                   ORDER BY s.domain, s.code
                   LIMIT %s""",
                (grade_level, f"%{subject}%", limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
            if rows:
                log.info(
                    f"[CurrGen] No {state_code} standards found for {grade_level} {subject}, "
                    f"using Common Core ({len(rows)} standards)"
                )

        return rows
    finally:
        cur.close()
        conn.close()


def _extract_json(text: str) -> dict | list | None:
    """Extract JSON from a Claude response."""
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
    # Find outermost { or [
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            break
    return None


def generate_curriculum_from_standards(
    grade_level: str,
    subject: str,
    state_code: str,
    scope: str = "full_year",
    teacher_id: str = "00000000-0000-0000-0000-000000000001",
    class_id: str | None = None,
) -> dict:
    """
    Build a curriculum from state standards already in the database.

    Args:
        grade_level: e.g., "4", "K", "7"
        subject: e.g., "Math", "ELA", "Science"
        state_code: e.g., "OH", "TX", "CA"
        scope: "full_year" or "next_unit"
        teacher_id: owner teacher ID
        class_id: optional class to attach the curriculum to

    Returns:
        dict with units (list of generated curriculum_calendar entries),
        framework_name, and metadata.
    """
    log.info(
        f"[CurrGen] Generating {scope} curriculum: "
        f"grade={grade_level} subject={subject} state={state_code}"
    )

    # 1. Fetch standards
    standards = _fetch_state_standards(state_code, grade_level, subject)
    if not standards:
        return {
            "error": f"No standards found for {state_code} grade {grade_level} {subject}. "
                     f"Check that the state framework is loaded.",
            "units": [],
        }

    framework_name = standards[0].get("framework_name", f"{state_code} Standards")
    log.info(f"[CurrGen] Found {len(standards)} standards from {framework_name}")

    # 2. Group standards into units via Sonnet
    client = _get_client()

    standards_text = "\n".join(
        f"- {s['code']}: {s['description']}"
        + (f" [Domain: {s['domain']}]" if s.get("domain") else "")
        for s in standards
    )

    if scope == "next_unit":
        unit_instruction = (
            "Generate ONLY the first unit (the one a teacher would start the year with). "
            "Include 4-8 standards that logically belong together. "
            "Estimate 2-4 weeks for this unit."
        )
    else:
        unit_instruction = (
            "Group ALL these standards into 6-10 logical teaching units that span "
            "a full school year (~36 weeks). Each unit should have 3-8 standards "
            "that are conceptually related and taught together. Order the units in "
            "the sequence a typical teacher would teach them (foundational concepts "
            "first, building complexity). Estimate weeks per unit (should total ~36)."
        )

    system = (
        f"You are an expert curriculum designer for grade {grade_level} {subject}. "
        f"You create scope and sequence documents that group standards into teachable "
        f"units in a logical progression. You know how teachers actually sequence their "
        f"year — foundational skills first, building to more complex applications."
    )

    user = f"""Create a curriculum scope and sequence for grade {grade_level} {subject}.

FRAMEWORK: {framework_name}
STANDARDS ({len(standards)} total):
{standards_text}

{unit_instruction}

Return a JSON object:
{{
  "units": [
    {{
      "unit_number": 1,
      "unit_name": "descriptive unit name",
      "topic": "brief topic description",
      "estimated_weeks": 3,
      "standards": ["CODE1", "CODE2", "CODE3"],
      "rationale": "one sentence on why these standards group together and why this unit comes here in the sequence"
    }}
  ]
}}

IMPORTANT:
- Every standard must appear in exactly one unit (don't skip any, don't duplicate)
- Unit names should be teacher-friendly (e.g., "Fractions: Building Understanding" not "NF Domain Standards")
- The sequence should reflect how teachers actually teach, not the alphabetical order of standard codes
- Foundational/prerequisite concepts come before dependent ones
- Respond with ONLY the JSON object"""

    try:
        resp = client.messages.create(
            model=SONNET,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        result = _extract_json(resp.content[0].text)
    except Exception as e:
        log.error(f"[CurrGen] Sonnet call failed: {e}")
        return {"error": f"Curriculum generation failed: {str(e)}", "units": []}

    if not result or not result.get("units"):
        return {"error": "Could not parse curriculum from AI response", "units": []}

    generated_units = result["units"]
    log.info(f"[CurrGen] Generated {len(generated_units)} units")

    # 3. Store in curriculum_calendar
    if class_id:
        stored_units = _store_generated_curriculum(
            class_id=class_id,
            teacher_id=teacher_id,
            units=generated_units,
            framework_name=framework_name,
        )

        # Mark the class as having a curriculum
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """UPDATE class_intelligence
                   SET has_curriculum = true,
                       current_calendar_id = (
                           SELECT calendar_id FROM curriculum_calendar
                           WHERE class_id = %s
                           ORDER BY COALESCE(sort_order, week_number) ASC
                           LIMIT 1
                       )
                   WHERE class_id = %s""",
                (class_id, class_id),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            log.warning(f"[CurrGen] Failed to update class_intelligence: {e}")
        finally:
            cur.close()
            conn.close()
    else:
        stored_units = generated_units

    return {
        "units": stored_units,
        "framework_name": framework_name,
        "state_code": state_code,
        "grade_level": grade_level,
        "subject": subject,
        "scope": scope,
        "standards_count": len(standards),
        "units_count": len(generated_units),
        "class_id": class_id,
        "generation_source": "ai_generated",
    }


def _store_generated_curriculum(
    class_id: str,
    teacher_id: str,
    units: list[dict],
    framework_name: str,
) -> list[dict]:
    """Store generated units in curriculum_calendar."""
    conn = get_connection()
    cur = conn.cursor()
    stored = []
    try:
        for unit in units:
            calendar_id = str(uuid4())
            unit_number = unit.get("unit_number", 0)
            cur.execute(
                """INSERT INTO curriculum_calendar
                   (calendar_id, class_id, week_number, unit_name, topic,
                    standards_scheduled, pacing_notes, is_assessment_week,
                    unit_status, sort_order, generation_source)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, false,
                           'planned', %s, 'ai_generated')""",
                (
                    calendar_id,
                    class_id,
                    unit_number,
                    unit.get("unit_name", f"Unit {unit_number}"),
                    unit.get("topic", ""),
                    Json(unit.get("standards", [])),
                    unit.get("rationale", ""),
                    unit_number,
                ),
            )
            stored.append({
                "calendar_id": calendar_id,
                "unit_number": unit_number,
                "unit_name": unit.get("unit_name"),
                "topic": unit.get("topic"),
                "standards": unit.get("standards", []),
                "estimated_weeks": unit.get("estimated_weeks"),
                "rationale": unit.get("rationale"),
            })

        conn.commit()
        log.info(f"[CurrGen] Stored {len(stored)} units for class {class_id}")
    except Exception as e:
        conn.rollback()
        log.error(f"[CurrGen] Failed to store curriculum: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    return stored
