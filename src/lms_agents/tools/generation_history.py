"""
Generation History — ensures content never repeats.

After every successful generation, stores a fingerprint + summary.
Before generating, queries history to build an exclusion list.
Default freshness window: 6 months.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


def store_generation(
    teacher_id: str,
    assignment_id: str,
    standard_codes: list[str],
    output_template_id: str,
    content: dict,
) -> str:
    """
    Store a generation record after successful content creation.

    Extracts fingerprint, summary, question texts, and vocabulary
    from the content dict. Returns the history_id.
    """
    questions = content.get("questions", [])
    question_texts = [q.get("question_text", "") for q in questions]
    vocabulary = list({
        word for q in questions
        for word in (q.get("answer", "").split() if q.get("answer") else [])
        if len(word) > 3
    })

    # Content fingerprint: hash of all question texts for exact-match detection
    content_str = json.dumps(question_texts, sort_keys=True)
    fingerprint = hashlib.sha256(content_str.encode()).hexdigest()[:32]

    # Brief summary for semantic comparison
    title = content.get("title", "")
    summary = f"{title}. Questions cover: " + "; ".join(
        q.get("question_text", "")[:60] for q in questions[:5]
    )
    if len(questions) > 5:
        summary += f" ... and {len(questions) - 5} more"

    conn = get_connection()
    cur = conn.cursor()
    history_id = str(uuid4())

    try:
        cur.execute(
            """INSERT INTO generation_history
               (history_id, teacher_id, assignment_id, standard_codes,
                output_template_id, content_fingerprint, content_summary,
                question_texts, vocabulary_used)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)""",
            (
                history_id, teacher_id, assignment_id,
                Json(standard_codes), output_template_id,
                fingerprint, summary,
                Json(question_texts), Json(vocabulary),
            ),
        )
        conn.commit()
        log.info(f"[History] Stored generation {history_id} (fingerprint: {fingerprint[:8]}...)")
    except Exception as e:
        conn.rollback()
        log.error(f"[History] Failed to store: {e}")
    finally:
        cur.close()
        conn.close()

    return history_id


def query_history(
    teacher_id: str,
    standard_codes: list[str],
    freshness_months: int = 6,
    output_template_id: str | None = None,
) -> list[dict]:
    """
    Query generation history for a teacher + standards within the freshness window.

    Returns list of previous generations with summaries and question texts
    for use as an exclusion list.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cutoff = datetime.now() - timedelta(days=freshness_months * 30)

    conditions = [
        "teacher_id = %s::uuid",
        "created_at > %s",
    ]
    params = [teacher_id, cutoff]

    if standard_codes:
        # Match any overlap between stored codes and query codes
        conditions.append("standard_codes ?| %s")
        params.append(standard_codes)

    if output_template_id:
        conditions.append("output_template_id = %s")
        params.append(output_template_id)

    where = " AND ".join(conditions)

    cur.execute(
        f"""SELECT history_id, content_summary, question_texts,
                   vocabulary_used, content_fingerprint, output_template_id,
                   standard_codes, created_at
            FROM generation_history
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT 20""",
        params,
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    log.info(f"[History] Found {len(rows)} previous generations for exclusion")
    return rows


def build_exclusion_prompt(history: list[dict]) -> str:
    """
    Build a prompt section that tells the Content Agent what NOT to generate.
    """
    if not history:
        return ""

    lines = ["\n\nIMPORTANT — DO NOT REPEAT PREVIOUS CONTENT:"]
    lines.append("The following questions and topics have already been generated for this teacher.")
    lines.append("You MUST create entirely NEW and DIFFERENT questions.\n")

    for i, h in enumerate(history[:10], 1):
        lines.append(f"Previous Generation #{i} ({h.get('output_template_id', 'unknown')}):")
        prev_questions = h.get("question_texts", [])
        for j, qt in enumerate(prev_questions[:5], 1):
            lines.append(f"  - Q{j}: {qt[:80]}")
        if len(prev_questions) > 5:
            lines.append(f"  ... and {len(prev_questions) - 5} more questions")
        lines.append("")

    lines.append("Generate COMPLETELY DIFFERENT questions with different scenarios, numbers, and contexts.")
    return "\n".join(lines)


def get_history_stats(teacher_id: str) -> dict:
    """Get summary stats of generation history for a teacher."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """SELECT
             COUNT(*) as total_generations,
             COUNT(DISTINCT output_template_id) as unique_templates,
             COUNT(DISTINCT content_fingerprint) as unique_fingerprints
           FROM generation_history
           WHERE teacher_id = %s::uuid""",
        (teacher_id,),
    )
    stats = dict(cur.fetchone())

    cur.execute(
        """SELECT jsonb_array_elements_text(standard_codes) as code,
                  COUNT(*) as gen_count
           FROM generation_history
           WHERE teacher_id = %s::uuid
           GROUP BY code
           ORDER BY gen_count DESC
           LIMIT 20""",
        (teacher_id,),
    )
    stats["standards_coverage"] = [dict(r) for r in cur.fetchall()]

    cur.close()
    conn.close()
    return stats
