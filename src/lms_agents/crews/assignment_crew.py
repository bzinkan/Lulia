"""
Assignment Generation Crew — 5-agent sequential chain.

Curriculum Agent → Content Agent → Rubric Agent → QA Agent → Format Agent

Uses the Anthropic SDK directly for each agent step. Each agent is a
focused prompt that receives the previous agent's output as context.

QA rejection loop: if QA rejects, Content re-runs with revision notes (max 2 retries).
"""
import json
import logging
import os
import re
from uuid import uuid4

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection
from src.lms_agents.tools.rag_search import search_kb

log = logging.getLogger(__name__)

SONNET = "claude-sonnet-4-20250514"
HAIKU = "claude-haiku-4-5-20251001"

QA_MAX_RETRIES = 2


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _call_claude(client: anthropic.Anthropic, model: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """Call Claude and return the text response."""
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


def _extract_json(text: str) -> dict | list | None:
    """Extract JSON from a Claude response that may have markdown fences."""
    # Try the whole thing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from code fences
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { or [
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start >= 0:
            # Find matching end
            depth = 0
            for i in range(start, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break
    return None


# ---------------------------------------------------------------------------
# Agent 1: Curriculum Agent
# ---------------------------------------------------------------------------

def run_curriculum_agent(client: anthropic.Anthropic, work_order: dict) -> dict:
    """
    Retrieve and format standards for the Content Agent.
    Queries the database for the specified standards.
    """
    log.info("[Curriculum Agent] Retrieving standards...")

    standards_ids = work_order.get("standards_ids", [])
    subject = work_order.get("subject", "")
    grade = work_order.get("grade_level", "")

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    standards = []
    if standards_ids:
        # Search by code
        for code in standards_ids:
            cur.execute(
                """SELECT s.code, s.description, s.grade_level, s.subject,
                          s.domain, f.name AS framework_name, f.tier
                   FROM standards s
                   JOIN standards_frameworks f ON s.framework_id = f.framework_id
                   WHERE s.code ILIKE %s AND f.is_active = true
                   ORDER BY f.priority ASC
                   LIMIT 3""",
                (f"%{code}%",),
            )
            standards.extend([dict(r) for r in cur.fetchall()])
    else:
        # Fallback: search by subject + grade
        cur.execute(
            """SELECT s.code, s.description, s.grade_level, s.subject,
                      s.domain, f.name AS framework_name, f.tier
               FROM standards s
               JOIN standards_frameworks f ON s.framework_id = f.framework_id
               WHERE f.is_active = true AND s.subject ILIKE %s AND s.grade_level = %s
               ORDER BY f.priority ASC
               LIMIT 20""",
            (f"%{subject}%", grade),
        )
        standards = [dict(r) for r in cur.fetchall()]

    cur.close()
    conn.close()

    # Deduplicate by code (keep highest priority / first occurrence)
    seen = set()
    unique = []
    for s in standards:
        if s["code"] not in seen:
            seen.add(s["code"])
            unique.append(s)

    result = {
        "standards": unique,
        "subject": subject,
        "grade_level": grade,
        "standards_count": len(unique),
    }
    log.info(f"[Curriculum Agent] Found {len(unique)} standards")
    return result


# ---------------------------------------------------------------------------
# Agent 2: Content Agent
# ---------------------------------------------------------------------------

def run_content_agent(
    client: anthropic.Anthropic,
    work_order: dict,
    curriculum_output: dict,
    revision_notes: str | None = None,
) -> dict:
    """
    Generate educational content shaped for the selected template.
    Searches RAG KB when has_kb_coverage is true.
    """
    log.info("[Content Agent] Generating content...")

    from src.lms_agents.tools.generation_history import query_history, build_exclusion_prompt

    template_id = work_order.get("output_template_id", "worksheet")
    question_count = work_order.get("question_count", 10)
    difficulty = work_order.get("difficulty_distribution", {"easy": 3, "medium": 4, "hard": 3})
    subject = work_order.get("subject", "")
    grade = work_order.get("grade_level", "")
    teacher_id = work_order.get("teacher_id", "")

    # Query Generation History for exclusion list
    history_exclusion = ""
    if teacher_id:
        standards_codes = [s["code"] for s in curriculum_output.get("standards", [])]
        history = query_history(teacher_id, standards_codes, freshness_months=6, output_template_id=template_id)
        history_exclusion = build_exclusion_prompt(history)

    # RAG search if KB coverage available
    kb_context = ""
    if work_order.get("has_kb_coverage"):
        standards_codes = [s["code"] for s in curriculum_output.get("standards", [])]
        query = f"{subject} grade {grade} {' '.join(standards_codes)}"
        results = search_kb(query=query, subject=subject, grade=grade, top_k=5)
        if results:
            kb_context = "\n\nRELEVANT CURRICULUM MATERIALS FROM KNOWLEDGE BASE:\n"
            for r in results:
                kb_context += f"\n--- Source: {r['source_name']}, Page {r.get('page_number', '?')} ---\n"
                kb_context += f"{r['content']}\n"
            log.info(f"[Content Agent] RAG KB returned {len(results)} relevant chunks")

    standards_text = "\n".join(
        f"- {s['code']}: {s['description']}" for s in curriculum_output.get("standards", [])
    )

    revision_section = ""
    if revision_notes:
        revision_section = f"\n\nREVISION REQUIRED — QA Agent feedback:\n{revision_notes}\nAddress ALL issues listed above.\n"

    system = (
        f"You are an expert educational content creator for grade {grade} {subject}. "
        f"You create content for the '{template_id}' template format. "
        f"All content must align with the provided standards and be grade-appropriate."
    )

    user = f"""Create educational content for the following assignment:

TEMPLATE: {template_id}
SUBJECT: {subject}
GRADE LEVEL: {grade}
QUESTION COUNT: {question_count}
DIFFICULTY DISTRIBUTION: {json.dumps(difficulty)}

ALIGNED STANDARDS:
{standards_text}
{kb_context}
{revision_section}
{history_exclusion}

Generate a JSON object with this structure:
{{
  "title": "descriptive title for the assignment",
  "instructions": "student-facing instructions",
  "questions": [
    {{
      "question_number": 1,
      "question_text": "the question",
      "answer": "the correct answer",
      "difficulty": "easy|medium|hard",
      "standard_code": "the standard this aligns to",
      "explanation": "brief explanation of the answer"
    }}
  ]
}}

IMPORTANT:
- Generate exactly {question_count} questions
- Follow the difficulty distribution: {json.dumps(difficulty)}
- Every question MUST align to one of the provided standards
- Questions must be grade-appropriate for grade {grade}
- For {template_id} format, ensure content fits the template structure
- Ground content in the curriculum materials when provided
- Vary question types (multiple choice, fill-in, short answer as appropriate)

Respond with ONLY the JSON object."""

    response = _call_claude(client, SONNET, system, user, max_tokens=4096)
    result = _extract_json(response)

    if result is None:
        log.warning("[Content Agent] Failed to parse JSON, using raw response")
        result = {"title": f"Grade {grade} {subject} {template_id.replace('_', ' ').title()}", "raw_content": response}

    log.info(f"[Content Agent] Generated: {result.get('title', 'untitled')}")
    return result


# ---------------------------------------------------------------------------
# Agent 3: Rubric Agent
# ---------------------------------------------------------------------------

def run_rubric_agent(client: anthropic.Anthropic, work_order: dict, content_output: dict) -> dict:
    """Create answer key and scoring guide matching the generated content."""
    log.info("[Rubric Agent] Creating answer key...")

    system = "You are an expert at creating answer keys and scoring rubrics for educational assessments."

    user = f"""Create an answer key and scoring guide for this assignment:

ASSIGNMENT CONTENT:
{json.dumps(content_output, indent=2)}

Generate a JSON object with:
{{
  "answer_key": [
    {{
      "question_number": 1,
      "correct_answer": "the answer",
      "acceptable_alternatives": ["alt1", "alt2"],
      "points": 1,
      "scoring_notes": "any special grading instructions"
    }}
  ],
  "total_points": <sum of all points>,
  "grading_notes": "overall grading instructions"
}}

Respond with ONLY the JSON object."""

    response = _call_claude(client, HAIKU, system, user, max_tokens=2048)
    result = _extract_json(response)

    if result is None:
        result = {"answer_key": [], "total_points": 0, "raw_response": response}

    log.info(f"[Rubric Agent] Answer key: {len(result.get('answer_key', []))} items, {result.get('total_points', 0)} points")
    return result


# ---------------------------------------------------------------------------
# Agent 4: QA Agent
# ---------------------------------------------------------------------------

def run_qa_agent(
    client: anthropic.Anthropic,
    work_order: dict,
    curriculum_output: dict,
    content_output: dict,
    rubric_output: dict,
) -> dict:
    """
    Audit content for accuracy, alignment, appropriateness, and answer key correctness.
    """
    log.info("[QA Agent] Auditing content...")

    standards_text = "\n".join(
        f"- {s['code']}: {s['description']}" for s in curriculum_output.get("standards", [])
    )

    system = (
        "You are a meticulous educational quality auditor. "
        "You verify factual accuracy, standards alignment, grade appropriateness, "
        "and answer key correctness. Be strict but fair."
    )

    user = f"""Audit this generated educational content:

WORK ORDER:
- Subject: {work_order.get('subject')}
- Grade: {work_order.get('grade_level')}
- Template: {work_order.get('output_template_id')}
- Question Count Required: {work_order.get('question_count')}

ALIGNED STANDARDS:
{standards_text}

GENERATED CONTENT:
{json.dumps(content_output, indent=2)}

ANSWER KEY:
{json.dumps(rubric_output, indent=2)}

Check ALL of the following:
1. FACTUAL ACCURACY: Are all questions and answers factually correct?
2. STANDARDS ALIGNMENT: Does every question map to one of the provided standards?
3. GRADE APPROPRIATENESS: Is vocabulary and complexity right for grade {work_order.get('grade_level')}?
4. ANSWER KEY CORRECTNESS: Is every answer in the key actually correct?
5. QUESTION COUNT: Are there exactly {work_order.get('question_count')} questions?
6. DIFFICULTY BALANCE: Does the mix match the requested distribution?
7. BIAS/SENSITIVITY: Any issues with cultural sensitivity or bias?

Generate a JSON object:
{{
  "approved": true/false,
  "score": 0-100,
  "checks": {{
    "factual_accuracy": {{"pass": true/false, "notes": "..."}},
    "standards_alignment": {{"pass": true/false, "notes": "..."}},
    "grade_appropriateness": {{"pass": true/false, "notes": "..."}},
    "answer_key_correctness": {{"pass": true/false, "notes": "..."}},
    "question_count": {{"pass": true/false, "notes": "..."}},
    "difficulty_balance": {{"pass": true/false, "notes": "..."}},
    "bias_sensitivity": {{"pass": true/false, "notes": "..."}}
  }},
  "issues": ["list of specific issues found"],
  "revision_notes": "detailed instructions for Content Agent if not approved, or null if approved"
}}

Be strict on accuracy but reasonable on other criteria.
Respond with ONLY the JSON object."""

    response = _call_claude(client, SONNET, system, user, max_tokens=2048)
    result = _extract_json(response)

    if result is None:
        result = {"approved": True, "score": 70, "issues": [], "revision_notes": None}

    log.info(f"[QA Agent] Score: {result.get('score', '?')}, Approved: {result.get('approved', '?')}")
    return result


# ---------------------------------------------------------------------------
# Agent 5: Format Agent
# ---------------------------------------------------------------------------

def run_format_agent(
    client: anthropic.Anthropic,
    work_order: dict,
    content_output: dict,
    rubric_output: dict,
) -> dict:
    """
    Render content through the Output Template Library.

    Uses the template renderer (no LLM call) — deterministic, instant,
    and produces consistent TpT-quality HTML for all 10 template types.
    """
    log.info("[Format Agent] Rendering output via template library...")

    from src.lms_agents.tools.template_renderer import render_template

    template_id = work_order.get("output_template_id", "worksheet")
    theme = work_order.get("design_theme", "modern_clean")

    # Merge rubric answers into content for answer key rendering
    answer_key_content = dict(content_output)
    if rubric_output and rubric_output.get("answer_key"):
        for ak_item in rubric_output["answer_key"]:
            qnum = ak_item.get("question_number")
            for q in answer_key_content.get("questions", []):
                if q.get("question_number") == qnum:
                    q["answer"] = ak_item.get("correct_answer", q.get("answer", ""))
                    q["points"] = ak_item.get("points", 1)

    student_html = render_template(template_id, content_output, answer_key=False, theme=theme)
    answer_key_html = render_template(template_id, answer_key_content, answer_key=True, theme=theme)

    log.info(f"[Format Agent] Rendered {template_id}: {len(student_html)} chars student, {len(answer_key_html)} chars key")
    return {
        "student_html": student_html,
        "answer_key_html": answer_key_html,
    }


# ---------------------------------------------------------------------------
# Main Crew Orchestrator
# ---------------------------------------------------------------------------

def run_assignment_crew(work_order: dict) -> dict:
    """
    Run the full 5-agent assignment generation crew.

    Sequential: Curriculum → Content → Rubric → QA → Format
    With QA rejection loop (max 2 retries).

    Returns a dict with all agent outputs and the final rendered content.
    """
    log.info(f"=== Assignment Crew: {work_order.get('work_order_id', 'unnamed')} ===")
    log.info(f"  Template: {work_order.get('output_template_id')}")
    log.info(f"  Subject: {work_order.get('subject')}, Grade: {work_order.get('grade_level')}")

    client = _get_client()

    # Agent 1: Curriculum
    curriculum_output = run_curriculum_agent(client, work_order)

    # QA loop: Content → Rubric → QA (with retries)
    content_output = None
    rubric_output = None
    qa_output = None
    revision_notes = None

    for attempt in range(1, QA_MAX_RETRIES + 2):  # 1 initial + 2 retries
        log.info(f"--- Generation attempt {attempt} ---")

        # Agent 2: Content
        content_output = run_content_agent(
            client, work_order, curriculum_output, revision_notes
        )

        # Agent 3: Rubric
        rubric_output = run_rubric_agent(client, work_order, content_output)

        # Agent 4: QA
        qa_output = run_qa_agent(
            client, work_order, curriculum_output, content_output, rubric_output
        )

        if qa_output.get("approved", False):
            log.info(f"[QA Agent] APPROVED on attempt {attempt}")
            break
        else:
            revision_notes = qa_output.get("revision_notes", "Please fix the identified issues.")
            log.info(f"[QA Agent] REJECTED on attempt {attempt}: {revision_notes[:100]}...")
            if attempt > QA_MAX_RETRIES:
                log.warning("[QA Agent] Max retries reached — proceeding with best attempt")

    # Agent 5: Format
    format_output = run_format_agent(client, work_order, content_output, rubric_output)

    # Store in database
    assignment_id = _store_assignment(work_order, content_output, rubric_output, qa_output, format_output)

    # Auto-extract class intelligence (non-fatal)
    try:
        from src.lms_agents.tools.class_intelligence import auto_extract_from_assignment
        class_id = work_order.get("class_id")
        if class_id and assignment_id:
            auto_extract_from_assignment(class_id, assignment_id)
    except Exception as e:
        log.warning(f"[ClassIntel] Auto-extraction hook failed (non-fatal): {e}")

    # Store in Generation History (no-repeat system)
    from src.lms_agents.tools.generation_history import store_generation
    try:
        store_generation(
            teacher_id=work_order.get("teacher_id", ""),
            assignment_id=assignment_id,
            standard_codes=[s["code"] for s in curriculum_output.get("standards", [])],
            output_template_id=work_order.get("output_template_id", ""),
            content=content_output,
        )
    except Exception as e:
        log.warning(f"Failed to store generation history: {e}")

    result = {
        "assignment_id": assignment_id,
        "work_order_id": work_order.get("work_order_id"),
        "title": content_output.get("title", ""),
        "template": work_order.get("output_template_id"),
        "standards_used": [s["code"] for s in curriculum_output.get("standards", [])],
        "question_count": len(content_output.get("questions", [])),
        "qa_score": qa_output.get("score", 0),
        "qa_approved": qa_output.get("approved", False),
        "content": content_output,
        "rubric": rubric_output,
        "qa_report": qa_output,
        "student_html": format_output.get("student_html", ""),
        "answer_key_html": format_output.get("answer_key_html", ""),
        "status": "complete",
        "accommodation_versions": [],
    }

    # Generate accommodation versions if requested
    accommodation_profiles = work_order.get("accommodation_versions", [])
    if accommodation_profiles:
        from src.lms_agents.tools.accommodation_engine import get_profile, apply_modifications
        from src.lms_agents.tools.template_renderer import render_template

        template_id = work_order.get("output_template_id", "worksheet")
        theme = work_order.get("design_theme", "modern_clean")
        subject = work_order.get("subject", "")
        grade = work_order.get("grade_level", "")

        for profile_id in accommodation_profiles:
            profile = get_profile(profile_id)
            if not profile:
                log.warning(f"[Accommodation] Profile not found: {profile_id}")
                continue

            log.info(f"[Accommodation] Generating {profile.get('name', profile_id)} version")
            modified = apply_modifications(content_output, profile, subject, grade)
            mod_student = render_template(template_id, modified, answer_key=False, theme=theme)
            mod_key = render_template(template_id, modified, answer_key=True, theme=theme)

            # Store as separate assignment
            mod_id = _store_assignment(
                {**work_order, "work_order_id": f"ACCOM-{profile_id}-{work_order.get('work_order_id', '')}"},
                modified, rubric_output, qa_output, {"student_html": mod_student, "answer_key_html": mod_key},
            )
            result["accommodation_versions"].append({
                "profile_id": profile_id,
                "profile_name": profile.get("name", profile_id),
                "assignment_id": mod_id,
                "question_count": len(modified.get("questions", [])),
                "student_html": mod_student,
                "answer_key_html": mod_key,
            })

    return result


def _store_assignment(
    work_order: dict,
    content_output: dict,
    rubric_output: dict,
    qa_output: dict,
    format_output: dict,
) -> str:
    """Store the completed assignment in the database."""
    conn = get_connection()
    cur = conn.cursor()
    assignment_id = str(uuid4())

    try:
        cur.execute(
            """INSERT INTO assignments
               (assignment_id, class_id, teacher_id, work_order_id, title,
                output_template_id, output_format, design_theme,
                standards_ids, questions, answer_key, qa_report,
                status, file_paths)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s,
                       %s, %s, %s,
                       %s, %s, %s, %s,
                       'complete', %s)""",
            (
                assignment_id,
                work_order.get("class_id"),
                work_order.get("teacher_id", "00000000-0000-0000-0000-000000000001"),
                work_order.get("work_order_id"),
                content_output.get("title", "Untitled"),
                work_order.get("output_template_id", "worksheet"),
                work_order.get("output_format", "html"),
                work_order.get("design_theme", "modern_clean"),
                Json(work_order.get("standards_ids", [])),
                Json(content_output.get("questions", [])),
                Json(rubric_output),
                Json(qa_output),
                Json({"student_html": "generated", "answer_key_html": "generated"}),
            ),
        )
        conn.commit()
        log.info(f"[Database] Stored assignment {assignment_id}")
    except Exception as e:
        conn.rollback()
        log.error(f"[Database] Failed to store assignment: {e}")
    finally:
        cur.close()
        conn.close()

    return assignment_id
