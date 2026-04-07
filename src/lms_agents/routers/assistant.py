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
    work_order = {
        "work_order_id": f"PROMPT-{os.urandom(4).hex()}",
        "class_id": req.class_id,
        "teacher_id": req.teacher_id,
        "output_template_id": "worksheet",
        "subject": params.get("subject", "Mathematics"),
        "grade_level": str(params.get("grade", "4")),
        "standards_ids": params.get("standards", []),
        "question_count": params.get("question_count", 10),
        "difficulty_distribution": {"easy": 3, "medium": 4, "hard": 3},
        "has_kb_coverage": True,
    }

    try:
        assignment_result = run_assignment_crew(work_order)
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
        result = generate_video(assignment_id, req.teacher_id)
        output_result["video"] = result

    output_result["parsed_intent"] = params
    return output_result
