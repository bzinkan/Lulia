"""
Assistant routes — parse natural language prompts into generation parameters,
and list existing assignments for the "From Existing" picker.
"""
import json
import logging
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

router = APIRouter(prefix="/assistant", tags=["Assistant"])

log = logging.getLogger(__name__)

# In-process cache for topic suggestions: {cache_key: (ts, suggestions)}
# Debounce/cancel handles most duplicate requests client-side, but a tiny
# server-side cache catches the rest (identical body across tabs, etc.).
_SUGGEST_CACHE: dict = {}
_SUGGEST_CACHE_TTL = 60  # seconds


def get_db():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )
    try:
        yield conn
    finally:
        conn.close()


# --- Assignment picker ---

@router.get("/assignments")
async def list_teacher_assignments(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    search: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    limit: int = Query(20),
    conn=Depends(get_db),
):
    """List teacher's assignments for the picker dropdown."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    conditions = ["a.teacher_id = %s::uuid", "a.status = 'complete'"]
    params = [teacher_id]
    if search:
        conditions.append("a.title ILIKE %s")
        params.append(f"%{search}%")
    if subject:
        conditions.append("a.output_template_id ILIKE %s")
        params.append(f"%{subject}%")
    where = " AND ".join(conditions)
    params.append(limit)
    cur.execute(
        f"""SELECT a.assignment_id, a.title, a.output_template_id, a.standards_ids,
                   a.design_theme, a.created_at, c.name as class_name, c.subject, c.grade_level,
                   jsonb_array_length(a.questions) as question_count
            FROM assignments a
            LEFT JOIN classes c ON a.class_id = c.class_id
            WHERE {where}
            ORDER BY a.created_at DESC LIMIT %s""",
        params,
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"assignments": rows}


# --- Intent parser ---

class ParseIntentRequest(BaseModel):
    prompt: str
    output_type: str = "interactive"  # interactive, game, video, worksheet


class GenerateFromPromptRequest(BaseModel):
    prompt: str
    output_type: str = "interactive"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    class_id: str = "00000000-0000-0000-0000-000000000010"
    auto_confirm: bool = False


@router.post("/parse-intent")
async def parse_intent(req: ParseIntentRequest):
    """Parse a natural language prompt into generation parameters."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse({"error": "API key not configured"}, status_code=500)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Map output types to available templates
    template_map = {
        "interactive": "multiple_choice_quiz, drag_drop_sort, matching_pairs, fill_in_blank, crossword_interactive, word_search_interactive, flash_cards_interactive, category_sort",
        "game": "classic_quiz, speed_race, team_tug_of_war, jeopardy, battle_royale, escape_classroom",
        "video": "video_lesson",
        "worksheet": "worksheet, task_cards, quiz_test, exit_ticket, bingo, flashcards, crossword, word_search, escape_room, board_game, reading_comprehension, study_guide",
    }

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": (
                f"Parse this teacher's request into generation parameters.\n\n"
                f'Request: "{req.prompt}"\n'
                f"Output type: {req.output_type}\n"
                f"Available templates for this type: {template_map.get(req.output_type, '')}\n\n"
                f"Respond with JSON:\n"
                f'{{"subject": "Mathematics|ELA|Science|Social Studies", "grade": "K|1-12", '
                f'"standards": ["code1"], "topic": "specific topic", '
                f'"output_template_id": "best matching template", '
                f'"question_count": 10, "difficulty": "medium", '
                f'"confidence": 0.0-1.0}}\n'
                f"Pick the BEST matching template. Infer standards from the topic and grade. "
                f"Set confidence based on how clearly the request specifies everything. "
                f"Respond with ONLY the JSON."
            )}],
        )
        text = resp.content[0].text.strip()
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            parsed = json.loads(match.group())
            conf = float(parsed.get("confidence", 0.5))
            parsed["needs_confirmation"] = conf < 0.8
            parsed["original_prompt"] = req.prompt
            parsed["output_type"] = req.output_type
            return parsed
    except Exception as e:
        log.error(f"[Intent] Parse failed: {e}")

    return {"error": "Could not parse prompt", "original_prompt": req.prompt}


@router.post("/generate-from-prompt")
async def generate_from_prompt(req: GenerateFromPromptRequest):
    """
    Two-step generation: parse intent → generate assignment → create output.
    Returns the final generated item (interactive activity, game session, or video).
    """
    # Step 1: Parse intent
    intent_req = ParseIntentRequest(prompt=req.prompt, output_type=req.output_type)
    from starlette.testclient import TestClient
    # Just call parse_intent directly
    import anthropic as _a
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse({"error": "API key not configured"}, status_code=500)

    client = _a.Anthropic(api_key=api_key)
    # Quick parse
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=256,
        messages=[{"role": "user", "content": (
            f'Parse: "{req.prompt}" for {req.output_type}.\n'
            f'JSON: {{"subject":"..","grade":"..","topic":"..","output_template_id":"..","question_count":10,"difficulty":"medium"}}'
        )}],
    )
    text = resp.content[0].text.strip()
    match = re.search(r"\{[\s\S]*?\}", text)
    if not match:
        return JSONResponse({"error": "Could not understand your prompt. Try being more specific."}, status_code=400)

    params = json.loads(match.group())

    # Step 2: Generate base assignment
    from src.lms_agents.crews.assignment_crew import run_assignment_crew
    # Map interactive templates to worksheet templates that naturally produce
    # the right question shape. MCQ activities need multiple-choice questions
    # with 4 options; most other interactive types work fine with the default
    # worksheet (short answers / fill-blanks).
    INTERACTIVE_TO_WORKSHEET = {
        "multiple_choice_quiz": "quiz_test",       # produces MC with 4 options
        "fill_in_blank":        "worksheet",       # short answers work
        "flash_cards_interactive": "vocab_cards",  # term/definition pairs
        "click_to_reveal":      "vocab_cards",     # same
    }
    target_interactive = params.get("output_template_id", "multiple_choice_quiz") if req.output_type == "interactive" else None
    base_template = (
        INTERACTIVE_TO_WORKSHEET.get(target_interactive, "worksheet")
        if req.output_type == "interactive" else "worksheet"
    )

    # Pull the teacher's topic back out of the Haiku parse — without this the
    # Content Agent was generating content shaped purely by RAG exemplars
    # and ignoring the teacher's actual subject matter.
    teacher_topic = (params.get("topic") or "").strip() or req.prompt.strip()

    work_order = {
        "work_order_id": f"PROMPT-{os.urandom(4).hex()}",
        "class_id": req.class_id,
        "teacher_id": req.teacher_id,
        "output_template_id": base_template,
        # Carry the intended interactive template forward so the Content
        # Agent can shape its output correctly (e.g. emit diagram_visual
        # for hotspot_labeling, matching pairs for matching_pairs, etc.)
        "interactive_template_id": target_interactive,
        # Authoritative topic — Content Agent must generate ON this topic,
        # not drift to whatever RAG exemplar it happens to match.
        "topic": teacher_topic,
        "original_prompt": req.prompt,
        "subject": params.get("subject", "Mathematics"),
        "grade_level": str(params.get("grade", "4")),
        "standards_ids": params.get("standards", []),
        "question_count": params.get("question_count", 10),
        "difficulty_distribution": {"easy": 3, "medium": 4, "hard": 3},
        "has_kb_coverage": True,
    }

    # Skip Format Agent (worksheet HTML rendering) for output types that build
    # their own HTML — interactive activities and games only consume the
    # question JSON. Saves 15-30s + Gemini tokens per generation.
    skip_format = req.output_type in ("interactive", "game")
    try:
        assignment_result = run_assignment_crew(work_order, skip_format=skip_format)
    except Exception as e:
        return JSONResponse({"error": f"Generation failed: {str(e)}"}, status_code=500)

    assignment_id = assignment_result.get("assignment_id")
    if not assignment_id:
        return JSONResponse({"error": "Assignment generation failed"}, status_code=500)

    # Step 3: Create the output (interactive, game, or video)
    output_result = {"assignment_id": assignment_id, "assignment": assignment_result}

    if req.output_type == "interactive":
        from src.lms_agents.tools.interactive_generator import generate_interactive_activity
        template_id = params.get("output_template_id", "multiple_choice_quiz")
        result = generate_interactive_activity(assignment_id, req.teacher_id, template_id)
        output_result["interactive"] = result

    elif req.output_type == "game":
        from src.lms_agents.tools.game_session_manager import create_game_session
        shell_id = params.get("output_template_id", "classic_quiz")
        result = create_game_session(req.teacher_id, assignment_id, shell_id)
        output_result["game"] = result

    elif req.output_type == "video":
        from src.lms_agents.crews.video_crew import generate_video
        result = generate_video(
            assignment_id, req.teacher_id,
            subject_override=params.get("subject"),
            grade_override=str(params.get("grade", "")),
        )
        output_result["video"] = result

    output_result["parsed_intent"] = params
    return output_result


# ---------------------------------------------------------------------------
# Topic suggestions (Pattern A — inline pills)
# ---------------------------------------------------------------------------
# Fired while teacher types a topic. Haiku returns 3 specific classroom-ready
# phrases that narrow the vague input. ~$0.0001 per call; server-side cached
# for 60s per (class_id, activity_type, partial_topic).

class TopicSuggestionsRequest(BaseModel):
    activity_type: str
    partial_topic: str
    class_id: Optional[str] = None
    teacher_id: str = "00000000-0000-0000-0000-000000000001"


_ACTIVITY_META = {
    "multiple_choice_quiz": "multiple-choice questions with 4 answer options each",
    "fill_in_blank": "sentences with blanks students fill from a word bank",
    "drag_drop_sort": "items students drag into 2 or more categories",
    "drag_drop_sequence": "items students reorder into a correct sequence",
    "category_sort": "items students drop into labeled buckets",
    "matching_pairs": "two columns students match (e.g. terms to definitions)",
    "click_to_reveal": "cards students click to reveal answers",
    "flash_cards_interactive": "term/definition flashcards students swipe through",
    "word_search_interactive": "a grid of letters with hidden words students find",
    "crossword_interactive": "a grid with word clues students type into",
    "number_line": "values students place on a number line",
    "slider_estimation": "values students estimate with a slider",
    "timeline_builder": "events students drag into chronological order",
    "whiteboard_response": "an open-response prompt students answer in free text",
    "hotspot_labeling": "a diagram students click to label specific parts",
}


@router.post("/topic-suggestions")
async def topic_suggestions(req: TopicSuggestionsRequest):
    """Return 3 specific topic phrases for a vague partial_topic."""
    import time
    if not req.partial_topic or len(req.partial_topic.strip()) < 3:
        return {"suggestions": []}

    cache_key = f"{req.class_id}|{req.activity_type}|{req.partial_topic.strip().lower()}"
    hit = _SUGGEST_CACHE.get(cache_key)
    if hit and (time.time() - hit[0]) < _SUGGEST_CACHE_TTL:
        return {"suggestions": hit[1]}

    # Resolve class context
    grade, subject, state_code = "5", "General", None
    class_intel_summary = None
    if req.class_id:
        try:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "db"),
                port=int(os.environ.get("DB_PORT", 5432)),
                dbname=os.environ.get("DB_NAME", "lulia"),
                user=os.environ.get("DB_USER", "lulia"),
                password=os.environ.get("DB_PASSWORD", "devpassword"),
            )
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """SELECT c.grade_level, c.subject, t.state_code
                   FROM classes c LEFT JOIN teachers t ON c.teacher_id = t.teacher_id
                   WHERE c.class_id = %s::uuid""",
                (req.class_id,),
            )
            row = cur.fetchone()
            if row:
                grade = row.get("grade_level") or grade
                subject = row.get("subject") or subject
                state_code = row.get("state_code")
            cur.close(); conn.close()
        except Exception as e:
            log.warning(f"[TopicSuggest] class lookup failed: {e}")

    activity_desc = _ACTIVITY_META.get(req.activity_type, req.activity_type)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"suggestions": []}

    prompt = (
        f"You help a Grade {grade} {subject} teacher"
        f"{f' in {state_code}' if state_code else ''} narrow a vague topic "
        f"into something specific enough to generate an interactive activity.\n\n"
        f"Selected activity: {req.activity_type} — {activity_desc}\n"
        f"Teacher typed: \"{req.partial_topic.strip()}\"\n\n"
        f"Return 3 specific, classroom-ready topic phrases that narrow what they "
        f"typed. Each phrase must be 2-6 words, grade-appropriate, and concrete "
        f"enough that generation can proceed without clarifying questions. Avoid "
        f"generic phrases like 'review of X' — suggest the underlying concept.\n\n"
        f"Respond with ONLY a JSON object: "
        f'{{"suggestions": ["...", "...", "..."]}} — no preamble, no markdown.'
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.content[0].text or "").strip()
        # Tolerant JSON parsing
        match = re.search(r"\{[\s\S]*\}", text)
        data = json.loads(match.group()) if match else {}
        sugg = data.get("suggestions", []) or []
        sugg = [s.strip() for s in sugg if isinstance(s, str) and s.strip()][:3]
        _SUGGEST_CACHE[cache_key] = (time.time(), sugg)
        return {"suggestions": sugg}
    except Exception as e:
        log.warning(f"[TopicSuggest] Haiku failed: {e}")
        return {"suggestions": []}
