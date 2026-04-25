"""
Gemini Interactive Generator — end-to-end content + diagram pipeline.

Replaces the 6-agent Sonnet crew (Curriculum → Pedagogy → Content → Rubric →
QA → Format) for interactive output types. Gemini 2.5 Pro produces the full
content JSON in one call — including the top-level `diagram_visual` for
hotspot_labeling activities — then the existing Gemini image pipeline
generates the diagram + hotspot coordinates.

Why: the Sonnet crew's RAG/Pedagogy brief/standards machinery frequently
drifted off-topic for interactive activities (pulling random grade-level
exemplars that overrode the teacher's actual topic). Interactive shapes are
narrow enough that a single well-prompted Gemini call beats the whole chain
on both correctness and speed.

Public entry point:
  generate_interactive_assignment(...) -> {activity_id, access_code,
                                            access_url, assignment_id,
                                            content}
"""
import json
import logging
import os
import re
from uuid import uuid4

log = logging.getLogger(__name__)

CONTENT_MODEL = "gemini-3.1-pro-preview"


def _gemini_client():
    from google import genai
    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


# Per-template directives — each tells Gemini how to shape its output for
# the specific interactive renderer that will consume it.
_TEMPLATE_DIRECTIVES = {
    "hotspot_labeling": """This is a HOTSPOT-LABELING activity — students click on labeled parts of a schematic SVG diagram. You are drawing a clean, structurally-accurate schematic (not photorealistic).

REQUIRED OUTPUT SHAPE:
{
  "title": "...",
  "instructions": "Click the named part on the diagram.",
  "diagram_svg": {
    "viewBox": "0 0 800 600",
    "background": "<SVG markup for any non-interactive background shapes — e.g. the cell wall outline, the overall organ silhouette. Optional.>",
    "parts": [
      {
        "id": "nucleus",
        "label": "Nucleus",
        "description": "The control center that contains DNA and directs cell activities.",
        "color": "#A855F7",
        "shape": "<ellipse cx='400' cy='300' rx='80' ry='70' />"
      },
      ...
    ]
  },
  "questions": [
    { "question_number": 1, "question_text": "Click the control center of the cell.", "answer_id": "nucleus", "difficulty": "easy|medium|hard", "explanation": "..." },
    ...
  ]
}

SVG / SHAPE RULES (critical — pixel-perfect clicks depend on this):
- viewBox is ALWAYS "0 0 800 600".
- Each part.shape is a SINGLE self-closing SVG element: <ellipse>, <circle>, <rect>, <polygon>, or <path>. No nesting, no transforms, no groups.
- Coordinates must place each part in its structurally-correct position for the real subject (e.g. in a plant cell: vacuole is the large central region; nucleus is nearby; mitochondria are scattered small ellipses; cell wall runs along the outer edge).
- Parts must NOT overlap each other's click regions — space them out. If a background shape encloses everything (cell wall, skin, outer boundary), put it in `background`, not `parts`.
- Each part.color is a distinct hex color (good contrast against white).
- Each part.id is lowercase-hyphenated and unique (e.g. "cell-wall", "left-ventricle").

QUESTION RULES:
- answer_id must exactly match one part.id.
- question_text should be a clue about function, not just naming the part — e.g. "Click the part that controls cell activities" (not "Click the nucleus"). This makes the activity educational, not trivial.
- Emit between 4 and 8 parts — the typical teachable count.
- Do NOT emit `options` arrays.
- Do NOT emit `answer` (the old field name) — use `answer_id` only.
""",
    "matching_pairs": """This is a MATCHING-PAIRS activity. Each question is one pair:
- `question_text` = left side (term / symbol / short phrase)
- `answer` = right side (matching term / definition / short phrase)

Both sides MUST be concise (1-6 words). Do NOT emit `options` arrays.
""",
    "number_line": """This is a NUMBER-LINE activity. Students place a value on a number line.

Every answer MUST be a single number (integer, decimal, or fraction). Include
`min` and `max` at the top level so the renderer knows the range:
{ "title": "...", "min": 0, "max": 20, "questions": [...] }
""",
    "multiple_choice_quiz": """This is a MULTIPLE-CHOICE QUIZ. Every question MUST have an `options` array
with 4 distinct choices, and `answer` MUST match exactly one option.
""",
    "fill_in_blank": """This is a FILL-IN-BLANK activity. Short answers (1-5 words). Use underscores
(____) in question_text to mark the blank location.
""",
    "flash_cards_interactive": """This is a FLASH-CARDS activity. Each question is a term/definition pair:
question_text = the term, answer = the definition. No options.
""",
    "click_to_reveal": """This is a CLICK-TO-REVEAL activity. Each question is a prompt / reveal pair:
question_text = the visible prompt, answer = the hidden content. No options.
""",
}


def _template_directive(template_id: str) -> str:
    return _TEMPLATE_DIRECTIVES.get(
        template_id,
        f"Shape the output for the '{template_id}' interactive template.",
    )


def _generate_content_json(
    topic: str,
    template_id: str,
    grade: str,
    subject: str,
    question_count: int,
    standards: list | None = None,
) -> dict:
    """Call Gemini 2.5 Pro to produce the full interactive content JSON."""
    directive = _template_directive(template_id)
    standards_text = ""
    if standards:
        lines = [f"- {s}" for s in standards if s]
        if lines:
            standards_text = "ALIGNED STANDARDS:\n" + "\n".join(lines) + "\n\n"

    prompt = f"""You are an expert K-12 educator creating an interactive {template_id} activity.

=== AUTHORITATIVE TOPIC (must be followed) ===
TOPIC: {topic}
SUBJECT: {subject}
GRADE LEVEL: {grade}
QUESTION COUNT: {question_count}
=== END TOPIC ===

{directive}

{standards_text}RULES:
- Every question MUST be about the TOPIC above. Do not drift.
- Generate EXACTLY {question_count} questions.
- Difficulty mix: 3 easy, 4 medium, 3 hard (adjust proportionally if count differs).
- Content must be grade-appropriate for grade {grade}.
- Output ONLY valid JSON. No preamble, no markdown fences, no commentary.
"""

    client = _gemini_client()
    resp = client.models.generate_content(
        model=CONTENT_MODEL,
        contents=[prompt],
    )
    text = (resp.text or "").strip()
    # Strip markdown fences if Gemini wrapped the JSON
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"Gemini returned no JSON: {text[:300]}")
    content = json.loads(match.group())

    # Normalize: some templates may omit `questions` (unlikely) — defensive default.
    content.setdefault("questions", [])
    content.setdefault("title", f"{subject} — {topic}")
    content.setdefault("instructions", "")
    return content


def _validate_svg_diagram(content: dict) -> dict:
    """
    Light validation of Gemini's diagram_svg output. Filters malformed parts
    without trying to fix them — the renderer handles missing/empty diagrams
    gracefully. Logs warnings so we can see when Gemini drifts.
    """
    dv = content.get("diagram_svg")
    if not isinstance(dv, dict):
        return content
    vb = str(dv.get("viewBox", "")).strip()
    if not re.match(r"^[\d\s.\-]+$", vb) or len(vb.split()) != 4:
        log.warning(f"[GeminiInteractive] Invalid viewBox '{vb}' — defaulting to 0 0 800 600")
        dv["viewBox"] = "0 0 800 600"
    raw_parts = dv.get("parts") or []
    cleaned = []
    seen_ids = set()
    for p in raw_parts:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id", "")).strip().lower()
        label = str(p.get("label", "")).strip()
        shape = str(p.get("shape", "")).strip()
        if not pid or not label or not shape:
            continue
        if pid in seen_ids:
            continue
        # Ensure shape starts with a valid SVG element tag
        if not re.match(r"^<\s*(ellipse|circle|rect|polygon|path)\b", shape, re.IGNORECASE):
            log.warning(f"[GeminiInteractive] Skipping part '{pid}' — shape not a simple SVG element")
            continue
        seen_ids.add(pid)
        cleaned.append({
            "id": pid,
            "label": label,
            "description": str(p.get("description", "")).strip(),
            "color": str(p.get("color", "#6B7280")).strip(),
            "shape": shape,
        })
    dv["parts"] = cleaned
    content["diagram_svg"] = dv

    # Filter questions to those whose answer_id matches a real part
    valid_ids = seen_ids
    kept_questions = []
    for q in content.get("questions") or []:
        if not isinstance(q, dict):
            continue
        aid = str(q.get("answer_id", "")).strip().lower()
        if aid and aid in valid_ids:
            q["answer_id"] = aid
            kept_questions.append(q)
    content["questions"] = kept_questions
    log.info(
        f"[GeminiInteractive] SVG diagram: {len(cleaned)} parts, "
        f"{len(kept_questions)} questions (valid answer_ids)"
    )
    return content


def _save_assignment_row(
    content: dict,
    teacher_id: str,
    class_id: str,
    template_id: str,
    standards: list | None = None,
) -> str:
    """
    Persist a minimal row in the `assignments` table so downstream code
    (refinement, sharing, class intelligence) has something to FK against.
    The `diagram_visual` field has no column here and is intentionally
    dropped — the interactive_activities.content_json carries the full
    payload that the activity HTML reads.
    """
    from psycopg2.extras import Json
    from src.lms_agents.tools.db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    assignment_id = str(uuid4())
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
                assignment_id, class_id, teacher_id,
                content.get("title", "Untitled"),
                template_id, "interactive", "modern_clean",
                Json(standards or []),
                Json(content.get("questions", [])),
                Json({}),
                Json({"approved": True, "score": 100, "source": "gemini_interactive"}),
                Json({"note": "interactive activity — no worksheet HTML"}),
            ),
        )
        conn.commit()
        log.info(f"[GeminiInteractive] Saved assignment {assignment_id}")
    except Exception as e:
        conn.rollback()
        log.error(f"[GeminiInteractive] Assignment insert failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()
    return assignment_id


def generate_interactive_assignment(
    topic: str,
    template_id: str,
    grade: str,
    subject: str,
    teacher_id: str,
    class_id: str,
    question_count: int = 10,
    standards: list | None = None,
    max_attempts: int = 3,
    show_answers_after: bool = True,
    time_limit: int | None = None,
) -> dict:
    """
    End-to-end Gemini interactive activity generation.

    Replaces the Sonnet crew → interactive_generator pipeline for interactive
    output types. Returns the same shape as generate_interactive_activity
    plus the raw content JSON.
    """
    log.info(
        f"[GeminiInteractive] topic='{topic[:60]}' template={template_id} "
        f"grade={grade} subject={subject} count={question_count}"
    )

    # 1. Generate content JSON
    content = _generate_content_json(
        topic=topic,
        template_id=template_id,
        grade=grade,
        subject=subject,
        question_count=question_count,
        standards=standards,
    )

    # 2. Validate inline SVG diagram (if present). No raster image gen —
    #    Gemini emits structurally-accurate SVG with labeled shapes that the
    #    renderer uses as pixel-perfect click regions.
    content = _validate_svg_diagram(content)

    # 3. Save minimal assignment row (FK target for downstream tables)
    assignment_id = _save_assignment_row(
        content=content,
        teacher_id=teacher_id,
        class_id=class_id,
        template_id=template_id,
        standards=standards,
    )

    # 4. Build + deploy the interactive HTML — reuse the existing deploy path,
    #    passing content_override so the Gemini content (with diagram_visual)
    #    is used directly instead of re-reading from the assignments table.
    from src.lms_agents.tools.interactive_generator import generate_interactive_activity
    activity = generate_interactive_activity(
        assignment_id=assignment_id,
        teacher_id=teacher_id,
        interactive_template_id=template_id,
        class_id=class_id,
        max_attempts=max_attempts,
        show_answers_after=show_answers_after,
        time_limit=time_limit,
        content_override=content,
    )

    return {
        **activity,
        "assignment_id": assignment_id,
        "content": content,
    }


# ============================================================================
# Artifact Mode — Gemini emits a complete self-contained HTML file per topic.
# The model picks the best UI for the subject. No fixed templates.
# ============================================================================

ARTIFACT_MODEL = "gemini-3.1-pro-preview"

# Canonical subjects where Gemini's trained knowledge beats any single
# library/Wikimedia image hit. For these topics we skip image lookup
# entirely so the model has no fallback but to draw a proper clickable
# SVG from first-principles anatomy.
_CANONICAL_SVG_TOPICS = [
    "plant cell", "animal cell", "eukaryotic cell", "prokaryotic cell",
    "cell organelle", "mitochondria", "chloroplast", "nucleus",
    "digestive system", "circulatory system", "respiratory system",
    "skeletal system", "nervous system", "muscular system",
    "heart", "lungs", "brain", "kidney",
    "neuron", "dna", "mitosis", "meiosis",
    "atom", "atomic structure", "periodic table",
    "water cycle", "rock cycle", "carbon cycle", "nitrogen cycle",
    "layers of the earth", "plate tectonic", "volcano",
    "solar system", "phases of the moon", "seasons",
    "photosynthesis", "cellular respiration",
    "polygon", "triangle", "angle", "coordinate plane",
]


def _is_canonical_svg_topic(topic: str) -> bool:
    """Return True if the topic is one Gemini can draw more accurately than
    any random library image match."""
    t = (topic or "").lower()
    return any(canon in t for canon in _CANONICAL_SVG_TOPICS)


_ARTIFACT_SYSTEM_PROMPT = """You are an expert K-12 educator and frontend engineer. Given a topic, produce a COMPLETE, self-contained interactive HTML learning activity — one file, ready to host.

TEMPLATE OBEDIENCE:
The teacher's TEMPLATE HINT is a CONTRACT for several specific UIs. When the hint is one of these, you MUST produce that exact interaction pattern — no substitutions, no "MCQ is easier":

- crossword        → a real crossword grid (interlocking across/down words, cells the student types into, a clues list with numbered prompts, highlight-current-word behavior)
- word_search      → a letter grid + word list; student clicks-drags to mark words
- flash_cards_interactive → card stack, tap to flip (term ↔ definition), swipe or next-button to advance
- click_to_reveal  → stacked prompts with hidden answers that reveal on click
- number_line      → horizontal line with ticks; student taps to place a value
- timeline         → horizontal timeline; student drags events into chronological order
- matching_pairs   → two columns, student connects / taps pairs
- fill_in_blank    → text passage with input fields for missing words
- hotspot_labeling → clickable labeled diagram (SVG groups as hit targets)
- multiple_choice_quiz → 4-option MCQ, one correct per question

For template hints NOT in the list above (e.g. "drag_drop_categories", "estimation_slider"), pick the best specific UI for the topic — but for any hint in the list, the UI is non-negotiable.

OUTPUT REQUIREMENTS:
1. Emit a single complete HTML file starting with `<!DOCTYPE html>` and ending with `</html>`.
2. Use React 18 + Babel standalone via unpkg CDN (these three <script> tags are allowed):
     https://unpkg.com/react@18/umd/react.production.min.js
     https://unpkg.com/react-dom@18/umd/react-dom.production.min.js
     https://unpkg.com/@babel/standalone/babel.min.js
3. All CSS inline in <style>. All JSX inline in one <script type="text/babel">.
4. NO external CSS/JS/fonts beyond Google Fonts and the three unpkg scripts above.
5. Use real, accurate structural/factual knowledge — you know biology, geography, math. Place parts in their real relative positions. Use correct terminology.
6. Self-score: track correct/incorrect per question, show a final results screen at the end with a big score + a "review" list. No server callback needed.
7. Mobile-responsive: the app must look good at 375px wide (phones) and 1024px wide (desktops).
8. Include a "Powered by Lulia AI" footer in small gray text.
9. Accessibility: cursor:pointer on clickables, sufficient color contrast, readable font sizes (≥14px body).

BRAND (match the Lulia design system):
- Background: #F5DEC3 (warm cream); card surfaces: #FEF9F2 (lighter cream).
- Primary accent: #F97316 (coral orange); hover: #EA580C.
- Text: #1C1917 (near-black); secondary: #78716C.
- Correct: #22C55E; wrong: #EF4444.
- Headings: 'DM Serif Display'; body: 'DM Sans'. Both from Google Fonts.
- Rounded corners (12-20px), soft shadows, generous padding.

VISUALS — DECIDE BETWEEN SVG AND IMAGES:

You have deep factual knowledge of canonical K-12 subjects. For these, DRAWING YOUR OWN SVG is better than any single library image — you can place every part exactly where it belongs, label it correctly, and make every shape a natively-clickable <g> (pixel-perfect hit regions, no coordinate mapping needed).

PREFER YOUR OWN INTERACTIVE SVG when the subject is:
- Plant or animal cell anatomy (organelles)
- Human body systems (digestive, circulatory, respiratory, skeletal)
- Cell biology structures (DNA, mitosis phases, neurons)
- Chemistry (atomic structure, molecular shapes, periodic table sections)
- Earth science (water cycle, rock cycle, layers of the Earth, plate tectonics)
- Astronomy (solar system, phases of the moon, seasons)
- Geometry (polygons, angles, triangles, coordinate planes)
- Any subject where the structure is standardized and universally taught

DRAWING RULES when emitting your own SVG:
- viewBox should be "0 0 800 600" or similar with good aspect ratio.
- Draw EVERY major labeled part — aim for 8-15 parts for anatomy, 5-10 for cycles.
- Each clickable part is a <g id="part-id" onClick=...> wrapping one SVG element. No nesting games.
- Place parts in their real anatomical/structural positions (nucleus centered, chloroplasts scattered in plant cells, small intestine below stomach, etc.).
- Use distinct, pedagogically-reasonable colors (not fluorescent; textbook-quality palettes).
- Add visible text labels connected by short leader lines (or show labels only on hover/click — your choice).
- Include enough detail that a 5th grader recognizes the subject, not a cartoon with 4 blobs.

USE A PROVIDED IMAGE (TEACHER LIBRARY or Wikimedia) when:
- The library block includes a top-ranked image AND the subject is niche or classroom-specific (a particular historical map, a teacher's photograph, a rare specimen).
- You're not confident you can draw an anatomically-correct version from knowledge alone.

When using an image, pair it with a sidebar of clickable labels (image as reference, sidebar as hit target — never try to overlay invisible click boxes on an image, alignment is brittle).

NEVER invent fake image URLs. If you don't use a provided URL, draw SVG.

RESPONSE FORMAT:
Return ONLY the HTML file contents. First character: `<`. Last character: `>`. No markdown code fences, no prose, no preamble, no trailing commentary."""


def _format_image_library(images: list[dict]) -> str:
    if not images:
        return (
            "=== TEACHER LIBRARY IMAGES ===\n"
            "No library matches found for this topic. Draw your own SVG.\n"
            "=== END LIBRARY ===\n"
        )
    lines = [
        "=== TEACHER LIBRARY IMAGES (YOU MUST USE THE FIRST URL BELOW) ===",
        "Use the TOP image as the primary visual via <img src='...' />.",
        "Do NOT draw your own SVG of this subject when a library image is",
        "provided — the teacher's image wins.",
        "",
    ]
    for i, img in enumerate(images):
        desc = (img.get("description") or "").strip().replace("\n", " ")
        tags = ", ".join(img.get("tags") or [])
        rank = "TOP CHOICE — USE THIS" if i == 0 else f"alternate #{i}"
        lines.append(f"[{rank}]")
        lines.append(f"  URL: {img['storage_url']}")
        lines.append(f"  Description: {desc}")
        if tags:
            lines.append(f"  Tags: {tags}")
        lines.append("")
    lines.append("=== END LIBRARY ===\n")
    return "\n".join(lines)


def _validate_artifact_html(html: str) -> list[str]:
    """Return a list of structural problems with the generated HTML.
    Empty list = passes. These are cheap syntactic checks — the real
    test is whether Babel parses the JSX, which we can't run server-side,
    but unbalanced braces/parens are the most common failure mode."""
    problems = []
    if len(html) < 500:
        problems.append("too short")
    if "<html" not in html.lower():
        problems.append("missing <html>")
    if "</html>" not in html.lower():
        problems.append("missing </html>")
    # Babel script present?
    if "babel" not in html.lower():
        problems.append("missing babel")
    # Brace / paren / bracket balance within the <script type="text/babel">
    m = re.search(r'<script[^>]*type\s*=\s*"text/babel"[^>]*>([\s\S]*?)</script>',
                  html, re.IGNORECASE)
    if not m:
        problems.append("missing JSX <script>")
    else:
        js = m.group(1)
        # Remove string + comment noise before counting
        js_clean = re.sub(r"//[^\n]*", "", js)
        js_clean = re.sub(r"/\*[\s\S]*?\*/", "", js_clean)
        js_clean = re.sub(r"(\"[^\"\\\\]*(?:\\\\.[^\"\\\\]*)*\")", "", js_clean)
        js_clean = re.sub(r"('[^'\\\\]*(?:\\\\.[^'\\\\]*)*')", "", js_clean)
        js_clean = re.sub(r"(`[^`\\\\]*(?:\\\\.[^`\\\\]*)*`)", "", js_clean)
        for open_ch, close_ch in [("{", "}"), ("(", ")"), ("[", "]")]:
            o = js_clean.count(open_ch)
            c = js_clean.count(close_ch)
            if o != c:
                problems.append(f"unbalanced {open_ch}{close_ch}: {o} open vs {c} close")
    return problems


def _generate_artifact_html(
    topic: str,
    template_hint: str,
    grade: str,
    subject: str,
    question_count: int,
    images: list[dict] | None = None,
    _retry: bool = True,
) -> str:
    """Call Gemini to produce a full HTML activity. Validates output and
    retries once on structural failures (the most common being unbalanced
    braces in Gemini's JSX). Raises on repeated failure."""
    from google.genai import types

    image_block = _format_image_library(images or [])
    user_prompt = f"""TOPIC: {topic}
SUBJECT: {subject}
GRADE LEVEL: {grade}
TEMPLATE HINT: {template_hint} (suggestion — pick the best UI for this topic)
TARGET QUESTION / INTERACTION COUNT: approximately {question_count}

{image_block}
Build the activity now. Output ONLY the HTML file."""

    client = _gemini_client()
    resp = client.models.generate_content(
        model=ARTIFACT_MODEL,
        contents=[user_prompt],
        config=types.GenerateContentConfig(
            system_instruction=_ARTIFACT_SYSTEM_PROMPT,
            max_output_tokens=32000,
            temperature=0.7,
        ),
    )
    html = (resp.text or "").strip()
    # Strip any stray markdown fences just in case
    html = re.sub(r"^```(?:html)?\s*", "", html)
    html = re.sub(r"```\s*$", "", html)
    if not html.lstrip().lower().startswith("<!doctype") and not html.lstrip().lower().startswith("<html"):
        m = re.search(r"(?is)(<!doctype[\s\S]*|<html[\s\S]*)", html)
        if m:
            html = m.group(1)
        else:
            raise ValueError(f"Gemini returned no HTML document: {html[:300]}")

    problems = _validate_artifact_html(html)
    if problems:
        log.warning(f"[GeminiArtifact] Output validation problems: {problems}")
        if _retry:
            log.info("[GeminiArtifact] Retrying once with a cleaner-output nudge")
            return _generate_artifact_html(
                topic=topic + " (ensure the JSX has balanced braces/parens — a prior attempt produced unbalanced syntax)",
                template_hint=template_hint,
                grade=grade, subject=subject,
                question_count=question_count,
                images=images,
                _retry=False,
            )
        # Last attempt also bad — raise so the caller surfaces the error
        raise ValueError(f"Gemini artifact failed validation: {problems}")
    return html


# Templates that bypass artifact mode and use a hand-written React engine.
# For these, Gemini produces DATA only — the UI/engine is deterministic code
# we own, so no LLM-written JS can crash at runtime.
_STRUCTURED_TEMPLATES = {
    "crossword",
    "word_search",
    "flash_cards_interactive",
    "timeline",
    "number_line",
    "fill_in_blank",
}


def generate_interactive_artifact(
    topic: str,
    template_id: str,
    grade: str,
    subject: str,
    teacher_id: str,
    class_id: str,
    question_count: int = 10,
    standards: list | None = None,
    max_attempts: int = 3,
    show_answers_after: bool = True,
    time_limit: int | None = None,
) -> dict:
    """
    Artifact-mode interactive generation. Gemini picks the UI and emits a
    complete self-contained HTML file. Returns the same shape as
    generate_interactive_assignment.

    For templates in _STRUCTURED_TEMPLATES, delegates to the hand-written
    engine for that template (zero LLM-written JS risk).
    """
    if template_id in _STRUCTURED_TEMPLATES:
        common_kwargs = dict(
            topic=topic, grade=grade, subject=subject,
            teacher_id=teacher_id, class_id=class_id,
            standards=standards, question_count=question_count,
        )
        if template_id == "crossword":
            from src.lms_agents.tools.structured_crossword import generate_crossword_activity
            return generate_crossword_activity(**common_kwargs)
        if template_id == "word_search":
            from src.lms_agents.tools.structured_wordsearch import generate_wordsearch_activity
            return generate_wordsearch_activity(**common_kwargs)
        if template_id == "flash_cards_interactive":
            from src.lms_agents.tools.structured_flashcards import generate_flashcards_activity
            return generate_flashcards_activity(**common_kwargs)
        if template_id == "timeline":
            from src.lms_agents.tools.structured_timeline import generate_timeline_activity
            return generate_timeline_activity(**common_kwargs)
        if template_id == "number_line":
            from src.lms_agents.tools.structured_number_line import generate_number_line_activity
            return generate_number_line_activity(**common_kwargs)
        if template_id == "fill_in_blank":
            from src.lms_agents.tools.structured_fill_blank import generate_fill_blank_activity
            return generate_fill_blank_activity(**common_kwargs)

    log.info(
        f"[GeminiArtifact] topic='{topic[:60]}' hint={template_id} "
        f"grade={grade} subject={subject} count={question_count}"
    )

    # 1. Look up images — UNLESS this is a canonical subject where Gemini's
    #    trained knowledge beats random library matches. For anatomy / cell
    #    biology / earth science etc, skipping the lookup forces Gemini to
    #    draw a proper clickable SVG from first principles (more accurate
    #    than Wikimedia's title-matched results, which are often mislabeled).
    images: list[dict] = []
    if _is_canonical_svg_topic(topic):
        log.info(f"[GeminiArtifact] Canonical topic '{topic[:40]}' — skipping image lookup to force SVG")
    else:
        try:
            from src.lms_agents.tools.image_library import find_best_images
            images = find_best_images(topic, teacher_id=teacher_id, limit=3)
        except Exception as e:
            log.warning(f"[GeminiArtifact] Image lookup failed (non-fatal): {e}")
            images = []

    # 2. Generate the complete HTML file
    html = _generate_artifact_html(
        topic=topic,
        template_hint=template_id,
        grade=grade,
        subject=subject,
        question_count=question_count,
        images=images,
    )

    # 3. Save a minimal assignment row for FK integrity (no questions JSON —
    #    the artifact is the source of truth; analytics on artifact mode
    #    come later if/when we add a score callback).
    from psycopg2.extras import Json
    from src.lms_agents.tools.db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    assignment_id = str(uuid4())
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
                assignment_id, class_id, teacher_id,
                f"{subject}: {topic}"[:200],
                template_id, "interactive_artifact", "gemini_choice",
                Json(standards or []),
                Json([]),
                Json({}),
                Json({"approved": True, "source": "gemini_artifact",
                      "images_used": [i.get("image_id") for i in images]}),
                Json({"note": "artifact-mode interactive"}),
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"[GeminiArtifact] Assignment insert failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    # 4. Deploy HTML to MinIO
    import boto3
    activity_id = str(uuid4())
    s3 = boto3.client(
        "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )
    bucket = os.environ.get("S3_BUCKET_ACTIVITIES", "lulia-activities")
    key = f"activities/{activity_id}/index.html"
    s3.put_object(Bucket=bucket, Key=key, Body=html.encode("utf-8"), ContentType="text/html; charset=utf-8")
    endpoint = os.environ.get("S3_PUBLIC_ENDPOINT") or os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    access_url = f"{endpoint}/{bucket}/{key}"

    # 5. Persist interactive_activities row so the activity shows up in the
    #    teacher's list. The access_code pattern matches the other generator.
    from secrets import choice
    import string as _string
    access_code = "".join(choice(_string.ascii_uppercase + _string.digits) for _ in range(6))

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
                Json({"mode": "artifact", "topic": topic, "subject": subject,
                      "grade": grade, "images_used": [i.get("image_id") for i in images]}),
                access_code, access_url,
                max_attempts, time_limit, show_answers_after,
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"[GeminiArtifact] activity insert failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    log.info(f"[GeminiArtifact] Deployed to {access_url}")

    return {
        "activity_id": activity_id,
        "assignment_id": assignment_id,
        "access_code": access_code,
        "access_url": access_url,
        "template": template_id,
        "mode": "artifact",
        "status": "live",
        "images_used": [i.get("storage_url") for i in images],
    }
