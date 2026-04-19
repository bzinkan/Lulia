"""
Assignment Generation Crew — 6-step sequential chain.

Curriculum Agent → Pedagogy Director → Content Agent → Rubric Agent → QA Agent → Format Agent

Uses the Anthropic SDK directly for each agent step. Each agent is a
focused prompt that receives the previous agent's output as context.

The Pedagogy Director is a grade-band expert that produces a Pedagogy Brief
(developmentally correct spec) which the Content and QA agents both honor.
If no pack exists for the requested grade band, the brief is None and the
crew falls back to un-constrained generation.

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
from src.lms_agents.tools.pedagogy_director import (
    format_brief_for_prompt,
    generate_brief,
)
from src.lms_agents.tools.rag_search import search_kb

log = logging.getLogger(__name__)

SONNET = "claude-sonnet-4-20250514"
HAIKU = "claude-haiku-4-5-20251001"

QA_MAX_RETRIES = 2

# Pattern: matches bracketed image references like [Image: ten-frame], [Picture: cat], [Diagram: cell]
_BRACKETED_IMAGE_RE = re.compile(
    r"\[(?:image|picture|diagram|illustration|graphic|visual|drawing|figure|photo|chart)[^\]]*\]",
    re.IGNORECASE,
)


def _detect_bracketed_visuals(content_output: dict) -> list[str]:
    """
    Scan question_text fields for bracketed visual descriptions like
    "[Image: ten-frame with 5 dots]". Returns a list of offending question
    references for the QA Agent's revision_notes. Empty list = clean.
    """
    violations = []
    for q in content_output.get("questions", []) or []:
        text = q.get("question_text", "") or ""
        if not text:
            continue
        for match in _BRACKETED_IMAGE_RE.finditer(text):
            qnum = q.get("question_number", "?")
            violations.append(f"Question {qnum}: '{match.group(0)}'")
    return violations


# Phrases that imply a visual IS present (the question refers to one).
# If question_text contains any of these AND the question has no `visual`
# field, the Content Agent is promising students something the renderer
# can't deliver.
_IMPLIED_VISUAL_RE = re.compile(
    r"\b(?:"
    r"look at (?:the |this )?(?:fraction model|model|diagram|figure|picture|image|"
    r"number line|array|chart|graph|table|shape)"
    r"|shown (?:below|above|here|in the)"
    r"|(?:the|this) (?:fraction model|model|diagram|figure|picture|image|"
    r"number line|array|chart|graph|table)"
    r"|based on (?:the|this) (?:figure|diagram|picture|image|model|graph|chart)"
    r"|use (?:the|this) (?:figure|diagram|picture|image|model|graph|chart|number line|array|fraction bar)"
    r"|count the (?:dots|shapes|objects|stars|circles|squares|blocks)"
    r"|identify the (?:shape|figure|angle|polygon)"
    r"|what (?:fraction|angle|shape) is shown"
    r"|the (?:shaded|highlighted|marked) (?:part|region|area|section|portion)"
    r")\b",
    re.IGNORECASE,
)


def _detect_missing_visuals(content_output: dict) -> list[str]:
    """
    Scan question_text for phrases that reference a visual (e.g. "look at
    the fraction model", "shown below", "count the dots"). If such a phrase
    is present but the question has no `visual` field, the student will see
    a broken question. Returns a list of offending references.
    """
    violations = []
    for q in content_output.get("questions", []) or []:
        text = q.get("question_text", "") or ""
        if not text:
            continue
        if q.get("visual"):
            continue  # Visual is attached — nothing implied
        m = _IMPLIED_VISUAL_RE.search(text)
        if m:
            qnum = q.get("question_number", "?")
            snippet = text[:100] + ("..." if len(text) > 100 else "")
            violations.append(f"Question {qnum} references '{m.group(0)}' but has no visual: {snippet}")
    return violations


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
    pedagogy_brief: dict | None = None,
    revision_notes: str | None = None,
    teacher_style: dict | None = None,
) -> dict:
    """
    Generate educational content shaped for the selected template.
    Searches RAG KB when has_kb_coverage is true.

    If a pedagogy_brief is provided, its constraints are injected into the
    prompt as authoritative. The Content Agent must honor every field in the
    brief — developmental constraints, vocabulary caps, banned terms, layout
    directives, and pedagogy notes.
    """
    log.info("[Content Agent] Generating content...")

    from src.lms_agents.tools.generation_history import query_history, build_exclusion_prompt

    template_id = work_order.get("output_template_id", "worksheet")
    interactive_template_id = work_order.get("interactive_template_id")
    question_count = work_order.get("question_count", 10)
    difficulty = work_order.get("difficulty_distribution", {"easy": 3, "medium": 4, "hard": 3})
    subject = work_order.get("subject", "")
    grade = work_order.get("grade_level", "")
    teacher_id = work_order.get("teacher_id", "")

    # If the pedagogy brief recommends a different template, honor it.
    if pedagogy_brief:
        recommended = pedagogy_brief.get("template_recommendation", {}).get("primary")
        if recommended and recommended != template_id:
            log.info(
                f"[Content Agent] Pedagogy brief recommends template '{recommended}' "
                f"over requested '{template_id}' — honoring brief"
            )
            template_id = recommended
            # Mutate the work order so the Format Agent renders the right template
            work_order["output_template_id"] = template_id

        # Also honor the problems-per-page cap from the brief.
        # Mutate the work order so the QA Agent's question_count check uses
        # the effective (brief-capped) count instead of the original request.
        max_problems = pedagogy_brief.get("layout_directives", {}).get("max_problems_per_page")
        if max_problems and question_count > max_problems:
            log.info(
                f"[Content Agent] Pedagogy brief caps at {max_problems} problems/page "
                f"(requested {question_count}) — capping"
            )
            question_count = max_problems
            work_order["question_count"] = max_problems

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

    # Inject textbook grounding from pre-fetched chunks (tagged with [TEXTBOOK])
    # These are the teacher's uploaded textbook chapters — authoritative content source
    textbook_chunks = [c for c in (work_order.get("_kb_chunks_injected") or []) if c.get("_is_textbook")]
    if not textbook_chunks and pedagogy_brief:
        # Check if the director attached any textbook chunks
        textbook_chunks = [c for c in (pedagogy_brief.get("_kb_chunks") or []) if c.get("_is_textbook")]

    if textbook_chunks:
        kb_context += "\n\nTEACHER'S TEXTBOOK (AUTHORITATIVE CONTENT SOURCE — use this vocabulary, "
        kb_context += "these examples, and these explanations as your primary content reference):\n"
        for tc in textbook_chunks:
            kb_context += f"\n--- {tc.get('source_name', 'Textbook')} ---\n"
            kb_context += f"{tc.get('content', '')}\n"
        log.info(f"[Content Agent] Textbook grounding: {len(textbook_chunks)} chunks (authoritative)")

    standards_text = "\n".join(
        f"- {s['code']}: {s['description']}" for s in curriculum_output.get("standards", [])
    )

    revision_section = ""
    if revision_notes:
        revision_section = f"\n\nREVISION REQUIRED — QA Agent feedback:\n{revision_notes}\nAddress ALL issues listed above.\n"

    # Inject the Pedagogy Brief as authoritative constraints
    brief_section = ""
    if pedagogy_brief:
        brief_section = "\n\n" + format_brief_for_prompt(pedagogy_brief) + "\n"

    # Inject teacher style profile if available
    style_section = ""
    if teacher_style:
        from src.lms_agents.tools.teacher_style_analyzer import format_style_for_prompt
        style_section = "\n\n" + format_style_for_prompt(teacher_style) + "\n"

    # Build an activity-type directive that overrides the generic template
    # guidance when the downstream output is a specialized interactive type.
    activity_directive = ""
    if interactive_template_id == "hotspot_labeling":
        activity_directive = (
            "\n\nCRITICAL: This content will power a HOTSPOT-LABELING interactive "
            "activity. You MUST emit a top-level `diagram_visual` field (NOT "
            "per-question) with type='hotspot_diagram', a subject string, and a "
            "parts list. Each question MUST be 'Click the <part>' with `answer` "
            "exactly matching one of the listed parts. Do NOT generate open-ended "
            "short-answer questions about the parts — the student answers by "
            "clicking on a generated diagram. See the HOTSPOT-LABELING ACTIVITIES "
            "section of the instructions for the exact shape."
        )
    elif interactive_template_id == "matching_pairs":
        activity_directive = (
            "\n\nCRITICAL: This content will power a MATCHING-PAIRS interactive "
            "activity. Each question becomes one pair where `question_text` is the "
            "left side and `answer` is the right side. Pairs should be concise — "
            "terms, symbols, or short phrases on each side. Either side can carry "
            "an optional `visual` or `answer_visual` for diagram-to-label matching. "
            "Do NOT emit `options` arrays — there's no multiple choice here."
        )

    system = (
        f"You are an expert educational content creator for grade {grade} {subject}. "
        f"You create content for the '{template_id}' template format."
        f"{activity_directive} "
        f"All content must align with the provided standards and be grade-appropriate. "
        f"When a Pedagogy Brief is provided, every field in it is AUTHORITATIVE — "
        f"honor vocabulary caps, banned terms, layout directives, assessment modes, "
        f"and scaffolding requirements without exception. "
        f"When the brief includes `reference_exemplar_guidance`, TREAT THE EXEMPLAR "
        f"SHAPE AS A TEMPLATE: match the question count, feature mix, scaffold pattern, "
        f"and structural shape of the referenced exemplar. Generate FRESH content — do "
        f"not copy verbatim — but stay in the same structural shape. The goal is "
        f"for your output to look like it came from the same teacher who made the "
        f"reference, not a generic AI worksheet. "
        f"When a question needs a visual (ten-frame, number line, fraction bar, etc.), "
        f"emit a STRUCTURED visual object on the question — never write bracketed text "
        f"like '[Image: ...]' or '[Picture: ...]' inside question_text. The visual "
        f"renderer converts your structured data into actual SVG graphics."
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
{brief_section}
{style_section}
{revision_section}
{history_exclusion}

Generate a JSON object with this structure:
{{
  "title": "descriptive title for the assignment",
  "instructions": "student-facing instructions",
  "questions": [
    {{
      "question_number": 1,
      "question_text": "the question (NEVER include bracketed image refs)",
      "answer": "the correct answer",
      "difficulty": "easy|medium|hard",
      "standard_code": "the standard this aligns to",
      "explanation": "brief explanation of the answer",
      "visual": {{ "type": "...", ... }}
    }}
  ]
}}

=== STRUCTURED VISUALS — REQUIRED FOR VISUAL CONTENT ===

NEVER write image descriptions in brackets inside question_text. Instead,
attach an OPTIONAL `visual` object to the question. The renderer will convert
it into an actual SVG image. If a question doesn't need a visual, omit the
field entirely.

If the Pedagogy Brief specifies "every_question_needs_image: true" (typical
for K-2), every question MUST have a `visual` object.

Available visual types and their schemas:

K-2 math (use heavily for 1st-2nd grade math):
  ten_frame:        {{"type": "ten_frame", "value": 5}}
  number_bond:      {{"type": "number_bond", "whole": 10, "part1": 7, "part2": 3}}
  counting_objects: {{"type": "counting_objects", "count": 6, "icon": "circle|square|star"}}
  base_ten_blocks:  {{"type": "base_ten_blocks", "hundreds": 1, "tens": 2, "ones": 4}}
  equation_box:     {{"type": "equation_box", "top": "24", "bottom": "17", "operator": "+"}}

3-5 math:
  fraction_bar:     {{"type": "fraction_bar", "numerator": 3, "denominator": 8}}
  fraction_circle:  {{"type": "fraction_circle", "numerator": 1, "denominator": 4}}
  array:            {{"type": "array", "rows": 4, "cols": 5}}
  bar_model:        {{"type": "bar_model", "parts": [{{"label": "12", "size": 3}}, {{"label": "?", "size": 2}}], "total": "20"}}
  area_model:       {{"type": "area_model", "row_parts": [20, 3], "col_parts": [10, 4]}}
  number_line:      {{"type": "number_line", "min": 0, "max": 10, "interval": 1, "highlights": [3]}}

6-12 math:
  coordinate_grid:  {{"type": "coordinate_grid", "x_min": -5, "x_max": 5, "y_min": -5, "y_max": 5,
                     "points": [{{"x": 2, "y": 3, "label": "A"}}], "lines": [{{"from": [-3, -2], "to": [3, 4]}}]}}
  function_table:   {{"type": "function_table", "rows": [{{"x": 1, "y": 3}}, {{"x": 2, "y": 5}}], "x_label": "x", "y_label": "y"}}

Geometry (3-12):
  polygon:          {{"type": "polygon", "sides": 6, "side_labels": ["5cm","5cm","5cm","5cm","5cm","5cm"], "label": "Regular hexagon"}}
                    OR with custom vertices and angle labels:
                    {{"type": "polygon", "vertices": [[0,0],[4,0],[0,3]], "side_labels": ["4","hypotenuse","3"], "angle_labels": ["90°","",""]}}
  angle:            {{"type": "angle", "degrees": 45, "measure_label": "45°"}}
                    (right angles get a square marker automatically; set `show_arc: false` to hide it)

Science (any grade):
  data_table:       {{"type": "data_table", "headers": ["Trial", "Mass"], "rows": [[1, "10g"], [2, "15g"]]}}
  labeled_diagram:  {{"type": "labeled_diagram", "subject": "plant cell", "labels": ["nucleus", "cell wall"]}}

ELA (K-2 heavy):
  letter_box:       {{"type": "letter_box", "letter": "B", "case": "both"}}
  word_box:         {{"type": "word_box", "word": "because"}}
  handwriting_lines: {{"type": "handwriting_lines", "lines": 3}}
  picture_choice:   {{"type": "picture_choice", "options": ["cat", "dog", "fish"]}}

You may add an optional "label" string to any visual to caption it.

=== WHEN TO USE VISUALS (strongly preferred for math/science) ===

For MATH questions, always prefer a structured visual when one of these
applies — even in grades 3-8. Visuals are not decoration; they give
students a grounded representation to reason from:

  - Question mentions a specific fraction       → fraction_bar OR fraction_circle
  - Comparing / ordering numbers                → number_line with highlights
  - Multiplication or area                      → array OR area_model
  - Addition/subtraction of multi-digit         → base_ten_blocks or equation_box
  - Part-part-whole or missing addend           → number_bond OR bar_model
  - Word problem with known/unknown parts       → bar_model
  - Counting or small quantity (K-2)            → counting_objects OR ten_frame
  - Plotting points / graphing lines            → coordinate_grid
  - Input/output tables                         → function_table
  - Naming a 2D shape / counting sides          → polygon (regular)
  - Classifying a triangle / shape with sides   → polygon with side_labels
  - Angle identification or measurement         → angle (with degrees)
  - Right-angle recognition                     → angle with degrees=90
    (square marker auto-added; use 45/135/etc. for acute/obtuse)

For SCIENCE questions with data or named structures:
  - Experimental results / observations         → data_table
  - Anatomy, cell parts, planet/ecosystem parts → labeled_diagram
  - HOTSPOT-LABELING activities (students click  → diagram_visual at the
    parts on a generated diagram)                  content level (see below)

For ELA in K-2:
  - Letter identification                       → letter_box
  - Sight word tracing / spelling               → word_box / handwriting_lines
  - Picture-based vocabulary                    → picture_choice

Skip visuals for pure text questions (e.g. "Define photosynthesis",
"Identify the theme"). If you're not sure whether a visual helps — it
probably does. Err on the side of including one.

=== HOTSPOT-LABELING ACTIVITIES (special case) ===

If the teacher's request is clearly a LABEL-THE-PARTS activity — e.g.
"label the parts of a plant cell", "identify the organs in the digestive
system", "label the water cycle stages" — emit a SINGLE shared diagram
at the CONTENT level (not per-question) using this shape:

{{
  "diagram_visual": {{
    "type": "hotspot_diagram",
    "subject": "<short description of the diagram, e.g. 'plant cell
                 cross-section', 'digestive system', 'water cycle'>",
    "parts": ["nucleus", "cell wall", "chloroplast", "vacuole",
              "cytoplasm"]
  }},
  "questions": [
    {{ "question_number": 1, "question_text": "Click the nucleus",
       "answer": "nucleus" }},
    {{ "question_number": 2, "question_text": "Click the chloroplast",
       "answer": "chloroplast" }},
    ...
  ]
}}

Rules for hotspot diagrams:
- Exactly ONE diagram_visual per activity (at the content level).
- Each question's answer MUST match one of the parts listed in
  diagram_visual.parts (case-insensitive).
- Each question_text should be "Click the <part>" or similar short
  command — the student answers by tapping on the diagram.
- Questions do NOT need their own `visual` field when the activity uses
  a shared hotspot diagram.
- Don't put `options` on these questions — there's no multiple choice,
  the answer is the click target.

=== END VISUALS ===

IMPORTANT:
- Generate exactly {question_count} questions
- Follow the difficulty distribution: {json.dumps(difficulty)}
- Every question MUST align to one of the provided standards
- Questions must be grade-appropriate for grade {grade}
- For {template_id} format, ensure content fits the template structure
- Ground content in the curriculum materials when provided
- Vary question types (multiple choice, fill-in, short answer as appropriate)
- If a PEDAGOGY BRIEF was provided above, every constraint is mandatory:
  vocabulary tier caps, banned terms, word problem contexts, scaffolds,
  sentence length, and assessment modes must ALL be honored
- NEVER write "[Image: ...]" or "[Picture: ...]" or "[Diagram: ...]" in
  question_text. Use the structured `visual` field instead.

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
    pedagogy_brief: dict | None = None,
) -> dict:
    """
    Audit content for accuracy, alignment, appropriateness, and answer key correctness.

    When a pedagogy_brief is provided, adds a Pedagogy Compliance check that
    validates the content against every authoritative rule in the brief
    (vocab caps, banned terms, layout directives, scaffolds, assessment modes).
    """
    log.info("[QA Agent] Auditing content...")

    standards_text = "\n".join(
        f"- {s['code']}: {s['description']}" for s in curriculum_output.get("standards", [])
    )

    brief_section = ""
    brief_check_line = ""
    brief_check_schema_entry = ""
    if pedagogy_brief:
        brief_section = "\n\n" + format_brief_for_prompt(pedagogy_brief) + "\n"
        brief_check_line = (
            "\n8. PEDAGOGY COMPLIANCE: Does the content honor EVERY rule in the "
            "Pedagogy Brief above? Check vocab tier caps, banned terms, word "
            "problem contexts, scaffolds, assessment modes, and layout directives. "
            "If ANY brief rule is violated, fail this check and reject."
        )
        brief_check_schema_entry = (
            ',\n    "pedagogy_compliance": {"pass": true/false, "notes": "..."}'
        )

    system = (
        "You are a meticulous educational quality auditor. "
        "You verify factual accuracy, standards alignment, grade appropriateness, "
        "answer key correctness, and (when provided) compliance with the "
        "authoritative Pedagogy Brief. Be strict but fair. "
        "Reject any content that contains bracketed image references in question_text "
        "(e.g. '[Image: ten-frame]' or '[Picture: cat]') — visuals must be in the "
        "structured `visual` field, not text descriptions."
    )

    user = f"""Audit this generated educational content:

WORK ORDER:
- Subject: {work_order.get('subject')}
- Grade: {work_order.get('grade_level')}
- Template: {work_order.get('output_template_id')}
- Question Count Required: {work_order.get('question_count')}

ALIGNED STANDARDS:
{standards_text}
{brief_section}
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
7. BIAS/SENSITIVITY: Any issues with cultural sensitivity or bias?{brief_check_line}

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
    "bias_sensitivity": {{"pass": true/false, "notes": "..."}}{brief_check_schema_entry}
  }},
  "issues": ["list of specific issues found"],
  "revision_notes": "detailed instructions for Content Agent if not approved, or null if approved"
}}

Be strict on accuracy AND pedagogy compliance. Be reasonable on other criteria.
Respond with ONLY the JSON object."""

    response = _call_claude(client, SONNET, system, user, max_tokens=2048)
    result = _extract_json(response)

    if result is None:
        result = {"approved": True, "score": 70, "issues": [], "revision_notes": None}

    # Deterministic post-check 1: bracketed image references in question_text
    # are an automatic rejection. The visual_renderer expects structured
    # `visual` objects on questions, never text descriptions like "[Image: ...]".
    # Post-check 2: questions whose text implies a visual ("look at the fraction
    # model", "count the dots", etc.) but has no visual field attached. The
    # student would see a broken question with a dangling reference.
    missing_visual_violations = _detect_missing_visuals(content_output)
    if missing_visual_violations:
        result["approved"] = False
        result.setdefault("checks", {})["implied_visual_missing"] = {
            "pass": False,
            "notes": f"Found {len(missing_visual_violations)} question(s) referencing a visual that isn't attached",
        }
        existing_issues = result.get("issues") or []
        result["issues"] = existing_issues + [
            f"Missing visual: {v}" for v in missing_visual_violations
        ]
        existing_notes = result.get("revision_notes") or ""
        missing_revision = (
            "These questions reference a visual in their text but have no "
            "`visual` field attached. For each one, either (a) attach the "
            "appropriate structured visual (fraction_bar, number_line, "
            "polygon, array, etc.) so the renderer can draw it, or (b) "
            "rewrite the question so it doesn't depend on a visual. "
            f"Violations: {'; '.join(missing_visual_violations[:3])}"
            + (f" (and {len(missing_visual_violations) - 3} more)" if len(missing_visual_violations) > 3 else "")
        )
        result["revision_notes"] = (
            (existing_notes + "\n\n" + missing_revision) if existing_notes else missing_revision
        )
        if result.get("score", 0) > 50:
            result["score"] = 50
        log.info(
            f"[QA Agent] DETERMINISTIC CHECK FAILED: {len(missing_visual_violations)} "
            f"questions reference missing visuals — forcing rejection"
        )

    bracket_violations = _detect_bracketed_visuals(content_output)
    if bracket_violations:
        result["approved"] = False
        result.setdefault("checks", {})["visual_format"] = {
            "pass": False,
            "notes": f"Found {len(bracket_violations)} bracketed image reference(s) in question_text",
        }
        existing_issues = result.get("issues") or []
        result["issues"] = existing_issues + [
            f"Bracketed image reference in {v}" for v in bracket_violations
        ]
        existing_notes = result.get("revision_notes") or ""
        bracket_revision = (
            "REMOVE all bracketed image references from question_text. "
            "Use the structured `visual` field on each question instead. "
            f"Violations: {'; '.join(bracket_violations[:5])}"
            + (f" (and {len(bracket_violations) - 5} more)" if len(bracket_violations) > 5 else "")
        )
        result["revision_notes"] = (
            (existing_notes + "\n\n" + bracket_revision) if existing_notes else bracket_revision
        )
        # Cap the score so it can't claim high quality when this is broken
        if result.get("score", 0) > 50:
            result["score"] = 50
        log.info(
            f"[QA Agent] DETERMINISTIC CHECK FAILED: {len(bracket_violations)} bracketed visuals — forcing rejection"
        )

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
    pedagogy_brief: str | None = None,
) -> dict:
    """
    Render content through the Output Template Library.

    Two renderer backends:
      - "gemini" (default): Gemini 2.5 Pro produces polished HTML in a single
        API call — mirrors the gemini.google.com Canvas UI output.
      - "python": legacy deterministic template renderer (no LLM call).

    Selected via WORKSHEET_RENDERER env var. Gemini failures fall back to
    Python so a generation never gets stuck without an HTML document.
    """
    renderer = os.environ.get("WORKSHEET_RENDERER", "gemini").lower()
    template_id = work_order.get("output_template_id", "worksheet")
    theme = work_order.get("design_theme", "modern_clean")

    log.info(f"[Format Agent] Rendering {template_id} via {renderer}...")

    if renderer == "gemini":
        try:
            from src.lms_agents.tools.gemini_worksheet_renderer import render_worksheet_html
            student_html = render_worksheet_html(
                template_id, content_output, rubric_output,
                pedagogy_brief=pedagogy_brief, work_order=work_order,
                answer_key=False, theme=theme,
            )
            answer_key_html = render_worksheet_html(
                template_id, content_output, rubric_output,
                pedagogy_brief=pedagogy_brief, work_order=work_order,
                answer_key=True, theme=theme,
            )
            log.info(
                f"[Format Agent] Gemini rendered {template_id}: "
                f"{len(student_html)} chars student, {len(answer_key_html)} chars key"
            )
            return {"student_html": student_html, "answer_key_html": answer_key_html}
        except Exception as e:
            log.warning(f"[Format Agent] Gemini renderer failed ({e}), falling back to Python template")

    # Python fallback (or explicitly selected)
    from src.lms_agents.tools.template_renderer import render_template

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

    log.info(
        f"[Format Agent] Python rendered {template_id}: "
        f"{len(student_html)} chars student, {len(answer_key_html)} chars key"
    )
    return {"student_html": student_html, "answer_key_html": answer_key_html}


# ---------------------------------------------------------------------------
# Main Crew Orchestrator
# ---------------------------------------------------------------------------

def _fetch_kb_chunks_for_brief(work_order: dict, curriculum_output: dict) -> list | None:
    """Pre-fetch RAG KB chunks so the Pedagogy Director can ground its brief."""
    if not work_order.get("has_kb_coverage"):
        return None
    try:
        subject = work_order.get("subject", "")
        grade = work_order.get("grade_level", "")
        standard_codes = [s["code"] for s in curriculum_output.get("standards", [])]
        query = f"{subject} grade {grade} {' '.join(standard_codes)}"
        return search_kb(query=query, subject=subject, grade=grade, top_k=5) or None
    except Exception as e:
        log.warning(f"[AssignmentCrew] RAG lookup for brief failed (non-fatal): {e}")
        return None


def _fetch_class_intel_prompt(work_order: dict) -> str | None:
    """Fetch the class intelligence AI context prompt for brief grounding."""
    class_id = work_order.get("class_id")
    if not class_id:
        return None
    try:
        from src.lms_agents.tools.class_intelligence import get_ai_context_prompt
        return get_ai_context_prompt(class_id) or None
    except Exception as e:
        log.warning(f"[AssignmentCrew] Class intelligence lookup failed (non-fatal): {e}")
        return None


def _fetch_reference_exemplars(work_order: dict, curriculum_output: dict) -> list | None:
    """
    Pre-fetch reference exemplars from the teacher archive + K-8 reference
    library so the Pedagogy Director can match real structural shapes.

    This is the core of reference-grounded generation: instead of letting
    the Content Agent hallucinate what a "2nd grade math worksheet" should
    look like, we retrieve real examples and tell the agent to match their
    shape with fresh content.
    """
    try:
        from src.lms_agents.tools.reference_retrieval import find_reference_exemplars

        subject = work_order.get("subject", "")
        grade = work_order.get("grade_level", "")
        template_id = work_order.get("output_template_id", "worksheet")

        # Build a topic query from the standards descriptions — that's what
        # the teacher actually wants to teach. Falls back to subject+grade.
        standards = curriculum_output.get("standards", []) or []
        if standards:
            topic_query = " ".join(
                s.get("description", "") for s in standards[:3]
            )[:500]
        else:
            topic_query = f"{subject} grade {grade}"

        # Map the requested output template to a canonical artifact_type.
        # If we don't know, leave None and the retriever will match any shape.
        artifact_type_map = {
            "worksheet": "worksheet",
            "task_cards": "task_cards",
            "exit_ticket": "assessment",
            "quiz_test": "assessment",
            "morning_work": "worksheet",
            "reading_comprehension": "reading_passage",
            "lab_activity": "lab_report",
            "graphic_organizer": "graphic_organizer",
            "study_guide": "reference_text",
            "flashcards": "other",
            "bingo": "game",
            "word_search": "game",
            "crossword": "game",
        }
        artifact_type = artifact_type_map.get(template_id)

        exemplars = find_reference_exemplars(
            topic_query=topic_query,
            grade=grade,
            subject=subject,
            artifact_type=artifact_type,
            teacher_id=work_order.get("teacher_id"),
            top_k=3,
        )
        if exemplars:
            log.info(
                f"[AssignmentCrew] Found {len(exemplars)} reference exemplars "
                f"(lanes: {set(e.get('upload_lane') for e in exemplars)})"
            )
        else:
            log.info(
                f"[AssignmentCrew] No reference exemplars found for "
                f"grade={grade} subject={subject} artifact={artifact_type}"
            )
        return exemplars or None
    except Exception as e:
        log.warning(f"[AssignmentCrew] Reference exemplar lookup failed (non-fatal): {e}")
        return None


def _fetch_textbook_grounding(work_order: dict, curriculum_output: dict) -> list | None:
    """
    Fetch textbook/reference_text chunks uploaded by the teacher.

    These are used differently from worksheet exemplars: textbook content
    provides vocabulary, examples, and explanations that the Content Agent
    should USE as its content source. Worksheet exemplars provide structural
    shape to match. This function returns the content source, not the shape.
    """
    try:
        from src.lms_agents.tools.reference_retrieval import find_reference_exemplars

        subject = work_order.get("subject", "")
        grade = work_order.get("grade_level", "")

        standards = curriculum_output.get("standards", []) or []
        if standards:
            topic_query = " ".join(s.get("description", "") for s in standards[:3])[:500]
        else:
            topic_query = f"{subject} grade {grade}"

        # Search specifically for reference_text (textbook chapters)
        textbook_chunks = find_reference_exemplars(
            topic_query=topic_query,
            grade=grade,
            subject=subject,
            artifact_type="reference_text",
            teacher_id=work_order.get("teacher_id"),
            top_k=3,
            lanes=["teacher_archive", "teacher_reference"],
        )

        if textbook_chunks:
            log.info(
                f"[AssignmentCrew] Found {len(textbook_chunks)} textbook grounding chunks "
                f"for {subject} grade {grade}"
            )
        return textbook_chunks or None
    except Exception as e:
        log.warning(f"[AssignmentCrew] Textbook grounding lookup failed (non-fatal): {e}")
        return None


def run_assignment_crew(work_order: dict, skip_format: bool = False) -> dict:
    """
    Run the full 6-step assignment generation crew.

    Sequential: Curriculum → Pedagogy Director → Content → Rubric → QA → Format
    With QA rejection loop (max 2 retries).

    When skip_format=True, the Format Agent (HTML rendering) is skipped.
    Use this when the caller only needs the question content — e.g.
    generate_interactive_activity builds its own HTML and throws away the
    worksheet render, so running Format Agent wastes 15-30s + Gemini tokens.

    Returns a dict with all agent outputs and (when not skipped) the final
    rendered content.
    """
    log.info(f"=== Assignment Crew: {work_order.get('work_order_id', 'unnamed')} ===")
    log.info(f"  Template: {work_order.get('output_template_id')}  (skip_format={skip_format})")
    log.info(f"  Subject: {work_order.get('subject')}, Grade: {work_order.get('grade_level')}")

    client = _get_client()

    # Step 1: Curriculum Agent — retrieve aligned standards
    curriculum_output = run_curriculum_agent(client, work_order)

    # Step 2: Pedagogy Director — generate developmentally-correct brief
    # Pre-fetch the inputs the director needs so its brief can be grounded.
    kb_chunks = _fetch_kb_chunks_for_brief(work_order, curriculum_output)
    class_intel_prompt = _fetch_class_intel_prompt(work_order)
    reference_exemplars = _fetch_reference_exemplars(work_order, curriculum_output)

    # Fetch teacher style profile (aggregated from their uploaded materials)
    teacher_style = None
    try:
        from src.lms_agents.tools.teacher_style_analyzer import get_teacher_style_profile
        tid = work_order.get("teacher_id")
        if tid:
            teacher_style = get_teacher_style_profile(tid)
            if teacher_style:
                log.info(
                    f"[AssignmentCrew] Teacher style: primary={teacher_style.get('primary_artifact_type')}, "
                    f"avg_questions={teacher_style.get('question_count_avg')}"
                )
    except Exception as e:
        log.warning(f"[AssignmentCrew] Teacher style lookup failed (non-fatal): {e}")

    # Fetch textbook grounding (reference_text artifacts from teacher uploads)
    textbook_grounding = _fetch_textbook_grounding(work_order, curriculum_output)
    if textbook_grounding:
        # Merge textbook excerpts into kb_chunks so the Content Agent sees them
        # but tagged as authoritative content sources, not just generic RAG hits
        if kb_chunks is None:
            kb_chunks = []
        for tg in textbook_grounding:
            kb_chunks.append({
                "source_name": f"[TEXTBOOK] {tg.get('source_name', '')}",
                "content": tg.get("excerpt", ""),
                "_is_textbook": True,
            })

    # Fetch curriculum context if the class has a curriculum
    curriculum_context = None
    try:
        from src.lms_agents.tools.class_intelligence import get_current_curriculum_context
        class_id = work_order.get("class_id")
        if class_id:
            curriculum_context = get_current_curriculum_context(class_id)
            if curriculum_context:
                log.info(
                    f"[AssignmentCrew] Curriculum context: unit={curriculum_context.get('current_unit')}, "
                    f"progress={curriculum_context.get('year_progress_pct')}%"
                )
    except Exception as e:
        log.warning(f"[AssignmentCrew] Curriculum context lookup failed (non-fatal): {e}")

    pedagogy_brief = generate_brief(
        work_order=work_order,
        curriculum_output=curriculum_output,
        kb_chunks=kb_chunks,
        class_intel_prompt=class_intel_prompt,
        reference_exemplars=reference_exemplars,
        curriculum_context=curriculum_context,
        client=client,
    )
    if pedagogy_brief is None:
        log.info("[AssignmentCrew] No pedagogy brief generated — running un-constrained")

    # QA loop: Content → Rubric → QA (with retries)
    content_output = None
    rubric_output = None
    qa_output = None
    revision_notes = None

    for attempt in range(1, QA_MAX_RETRIES + 2):  # 1 initial + 2 retries
        log.info(f"--- Generation attempt {attempt} ---")

        # Step 3: Content Agent (constrained by brief + teacher style)
        content_output = run_content_agent(
            client, work_order, curriculum_output, pedagogy_brief, revision_notes,
            teacher_style=teacher_style,
        )

        # Step 4: Rubric Agent
        rubric_output = run_rubric_agent(client, work_order, content_output)

        # Step 5: QA Agent (validates against brief)
        qa_output = run_qa_agent(
            client, work_order, curriculum_output, content_output, rubric_output, pedagogy_brief
        )

        if qa_output.get("approved", False):
            log.info(f"[QA Agent] APPROVED on attempt {attempt}")
            break
        else:
            revision_notes = qa_output.get("revision_notes", "Please fix the identified issues.")
            log.info(f"[QA Agent] REJECTED on attempt {attempt}: {revision_notes[:100]}...")
            if attempt > QA_MAX_RETRIES:
                log.warning("[QA Agent] Max retries reached — proceeding with best attempt")

    # Agent 5: Format — pass the pedagogy brief so the renderer (Gemini or
    # Python) can honor developmental visual constraints (font size, whitespace,
    # scaffolding intensity) per grade band.
    # Callers that only need the question JSON (e.g. interactive + game
    # generators that build their own HTML) can skip this step entirely.
    if skip_format:
        log.info("[Format Agent] SKIPPED (caller requested skip_format=True)")
        format_output = {"student_html": "", "answer_key_html": "", "skipped": True}
    else:
        brief_text = format_brief_for_prompt(pedagogy_brief) if pedagogy_brief else None
        format_output = run_format_agent(
            client, work_order, content_output, rubric_output,
            pedagogy_brief=brief_text,
        )

    # Store in database
    assignment_id = _store_assignment(work_order, content_output, rubric_output, qa_output, format_output)

    # Auto-extract class intelligence (non-fatal)
    try:
        from src.lms_agents.tools.class_intelligence import (
            auto_extract_from_assignment,
            log_standards_batch,
            auto_advance_position,
        )
        class_id = work_order.get("class_id")
        teacher_id = work_order.get("teacher_id", "")
        if class_id and assignment_id:
            auto_extract_from_assignment(class_id, assignment_id)

        # Always-on standard activity logging — fires even without a curriculum
        standard_codes = [s["code"] for s in curriculum_output.get("standards", []) if s.get("code")]
        if standard_codes and (class_id or teacher_id):
            log_standards_batch(
                class_id=class_id or "no_class",
                teacher_id=teacher_id,
                standard_codes=standard_codes,
                activity_type="assignment_generated",
                source_id=assignment_id,
            )

        # Auto-advance curriculum position if class has a curriculum
        if class_id:
            auto_advance_position(class_id)
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
        "pedagogy_brief": pedagogy_brief,
        "pedagogy_pack_id": (pedagogy_brief or {}).get("_pack_id"),
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
