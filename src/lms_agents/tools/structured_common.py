"""
Shared plumbing for hand-written structured activity templates.

Each structured template module owns:
  - A Gemini prompt that asks for DATA ONLY (no HTML).
  - An HTML template with the engine/React component (human-authored).
  - A thin public entry point.

This module provides what's common across all of them: the Gemini client,
the access-code generator, and the deploy-to-MinIO-and-DB step.
"""
import json
import logging
import os
import re
from secrets import choice
import string
from uuid import uuid4

log = logging.getLogger(__name__)

CONTENT_MODEL = "gemini-3.1-pro-preview"


def gemini_client():
    from google import genai
    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def generate_access_code(length: int = 6) -> str:
    return "".join(choice(string.ascii_uppercase + string.digits) for _ in range(length))


def get_builder(template_id: str):
    """Return the build_html(data) -> str function for a structured template.
    Raises ValueError for unknown template. Uses lazy imports to avoid
    circular-import risk with per-template modules."""
    if template_id == "crossword":
        from src.lms_agents.tools.structured_crossword import _build_crossword_html
        return _build_crossword_html
    if template_id == "word_search":
        from src.lms_agents.tools.structured_wordsearch import _build_html
        return _build_html
    if template_id == "flash_cards_interactive":
        from src.lms_agents.tools.structured_flashcards import _build_html
        return _build_html
    if template_id == "timeline":
        from src.lms_agents.tools.structured_timeline import _build_html
        return _build_html
    if template_id == "number_line":
        from src.lms_agents.tools.structured_number_line import _build_html
        return _build_html
    if template_id == "fill_in_blank":
        from src.lms_agents.tools.structured_fill_blank import _build_html
        return _build_html
    raise ValueError(f"Unknown structured template: {template_id}")


def fetch_grounding_context(
    topic: str,
    grade: str,
    subject: str,
    standards: list[str] | None = None,
    teacher_id: str | None = None,
    rag_top_k: int = 4,
    textbook_top_k: int = 2,
    excerpt_chars: int = 800,
) -> str:
    """
    Build a single ground-the-prompt block for structured-interactive
    generation. Pulls two sources:

      1. Textbook grounding — `find_reference_exemplars()` against the
         teacher's archive + reference lanes (their uploaded textbooks
         and reference samples). These are the AUTHORITATIVE content
         source — vocabulary and explanations win over the model prior.

      2. Topical RAG — `search_kb()` for general topical chunks that
         aren't tagged as reference_text. Looser match, broader source
         set, used as supporting context.

    Returns a string ready to interpolate into a Gemini prompt.
    Empty string if nothing relevant is found (graceful — generation
    still proceeds on Gemini's prior, same as before).
    """
    parts: list[str] = []
    seen_source_ids: set[str] = set()

    # ---- 1) Textbook grounding ----
    try:
        from src.lms_agents.tools.reference_retrieval import find_reference_exemplars
        textbooks = find_reference_exemplars(
            topic_query=topic,
            grade=str(grade or ""),
            subject=subject,
            artifact_type="reference_text",
            lanes=["teacher_archive", "teacher_reference"],
            teacher_id=teacher_id,
            top_k=textbook_top_k,
            include_excerpt=True,
            excerpt_max_chars=excerpt_chars,
        ) or []
    except Exception as e:
        log.warning(f"[Grounding] textbook lookup failed (non-fatal): {e}")
        textbooks = []

    if textbooks:
        parts.append(
            "=== TEACHER'S TEXTBOOK / REFERENCE MATERIAL (AUTHORITATIVE) ===\n"
            "Use the vocabulary, examples, and phrasing below as the primary\n"
            "source of truth for this activity. These are the teacher's own\n"
            "uploaded materials — match the grade-level voice and term choice."
        )
        for tb in textbooks:
            seen_source_ids.add(str(tb.get("source_id")))
            name = (tb.get("source_name") or "").strip()
            excerpt = (tb.get("excerpt") or "").strip()
            if not excerpt:
                continue
            parts.append(f"\n[{name or 'Reference'}]\n{excerpt}")
        parts.append("=== END TEXTBOOK ===\n")

    # ---- 2) Topical RAG (skip chunks already pulled as textbooks) ----
    try:
        from src.lms_agents.tools.rag_search import search_kb
        rag_hits = search_kb(query=topic, subject=subject, grade=grade, top_k=rag_top_k) or []
    except Exception as e:
        log.warning(f"[Grounding] RAG search failed (non-fatal): {e}")
        rag_hits = []

    rag_hits = [r for r in rag_hits if str(r.get("source_id")) not in seen_source_ids]

    if rag_hits:
        parts.append(
            "=== TOPICAL CONTEXT (supporting) ===\n"
            "Background context retrieved from the broader knowledge base.\n"
            "Use as supporting evidence; the textbook block above wins on\n"
            "any conflict."
        )
        for h in rag_hits[:rag_top_k]:
            name = (h.get("source_name") or "").strip()
            content = (h.get("content") or "").strip()
            if not content:
                continue
            # Keep each chunk short so the prompt doesn't blow past max_input
            snippet = content[:excerpt_chars]
            parts.append(f"\n[{name or 'Source'}]\n{snippet}")
        parts.append("=== END CONTEXT ===\n")

    if not parts:
        return ""
    log.info(
        f"[Grounding] {len(textbooks)} textbook chunks + {len(rag_hits)} "
        f"RAG hits for topic='{topic[:40]}'"
    )
    return "\n".join(parts) + "\n"


def call_gemini_json(prompt: str) -> dict:
    """Call Gemini for JSON output. Strips markdown fences, extracts the
    outermost JSON object. Raises ValueError if the response is unusable."""
    client = gemini_client()
    resp = client.models.generate_content(
        model=CONTENT_MODEL,
        contents=[prompt],
    )
    text = (resp.text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"Gemini returned no JSON: {text[:300]}")
    return json.loads(match.group())


def deploy_structured_activity(
    *,
    html: str,
    template_id: str,
    title: str,
    teacher_id: str,
    class_id: str,
    standards: list | None,
    content_summary: dict,
    full_data: dict | None = None,
    questions_for_assignment: list | None = None,
) -> dict:
    """
    Upload the HTML to MinIO and persist both the assignments row (FK target)
    and the interactive_activities row. Returns the standard activity info
    dict that the frontend expects.

    `content_summary` is stored on the interactive_activities row so admins /
    analytics can see what was generated without refetching the HTML.

    `full_data` is the complete template data dict (words+clues, cards, events,
    etc.). It's persisted inside content_json under the "data" key so the
    edit flow can round-trip: fetch data → let teacher edit → rebuild HTML.
    """
    import boto3
    from psycopg2.extras import Json
    from src.lms_agents.tools.db import get_connection

    assignment_id = str(uuid4())
    activity_id = str(uuid4())
    access_code = generate_access_code()

    # 1. assignments row
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO assignments
               (assignment_id, class_id, teacher_id, title,
                output_template_id, output_format, design_theme,
                standards_ids, questions, answer_key, qa_report,
                status, file_paths)
               VALUES (%s, %s::uuid, %s::uuid, %s,
                       %s, %s, %s,
                       %s, %s, %s, %s,
                       'complete', %s)""",
            (
                assignment_id, class_id, teacher_id, title,
                template_id, "interactive_structured", "lulia_default",
                Json(standards or []),
                Json(questions_for_assignment or []),
                Json({}),
                Json({"approved": True, "source": f"structured_{template_id}"}),
                Json({"note": f"structured {template_id}"}),
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # 2. MinIO upload
    s3 = boto3.client(
        "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )
    bucket = os.environ.get("S3_BUCKET_ACTIVITIES", "lulia-activities")
    key = f"activities/{activity_id}/index.html"
    s3.put_object(
        Bucket=bucket, Key=key,
        Body=html.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )
    endpoint = os.environ.get("S3_PUBLIC_ENDPOINT") or os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    access_url = f"{endpoint}/{bucket}/{key}"

    # 3. interactive_activities row
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO interactive_activities
               (activity_id, assignment_id, teacher_id, class_id,
                interactive_template_id, content_json, access_code, access_url,
                max_attempts, time_limit_seconds, show_answers_after, status)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'live')""",
            (
                activity_id, assignment_id, teacher_id, class_id,
                template_id,
                Json({"mode": "structured", "template": template_id,
                      "data": full_data or {},
                      **content_summary}),
                access_code, access_url,
                3, None, True,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    log.info(f"[Structured:{template_id}] Deployed to {access_url}")
    return {
        "activity_id": activity_id,
        "assignment_id": assignment_id,
        "access_code": access_code,
        "access_url": access_url,
        "template": template_id,
        "mode": "structured",
        "status": "live",
    }
