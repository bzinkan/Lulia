"""
Planning Crew — Lesson Planner Agent.

Reads class info, curriculum calendar, standards, Generation History, RAG KB coverage,
and Template Library catalog to produce a plan for a given duration.

Subject-aware template selection:
  - Math: worksheets, task cards, bingo, word search, board game
  - ELA: reading comprehension, writing prompts, vocab cards, crossword
  - Science: lab activity, graphic organizer, study guide, escape room
  - Social Studies: escape room, scavenger hunt, board game, study guide
"""
import json
import logging
import os
import re
from datetime import date, timedelta
from uuid import uuid4

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection
from src.lms_agents.tools.generation_history import query_history, build_exclusion_prompt
from src.lms_agents.tools.pedagogy_director import (
    format_brief_for_prompt,
    generate_brief,
)

log = logging.getLogger(__name__)

SONNET = "claude-sonnet-4-20250514"

SUBJECT_TEMPLATES = {
    "Mathematics": ["worksheet", "task_cards", "bingo", "word_search", "board_game", "exit_ticket", "flashcards", "morning_work", "quiz_test"],
    "Math": ["worksheet", "task_cards", "bingo", "word_search", "board_game", "exit_ticket", "flashcards", "morning_work", "quiz_test"],
    "ELA": ["reading_comprehension", "vocab_cards", "crossword", "flashcards", "writing_prompts", "word_search", "morning_work", "exit_ticket"],
    "English Language Arts": ["reading_comprehension", "vocab_cards", "crossword", "flashcards", "writing_prompts", "word_search", "morning_work", "exit_ticket"],
    "Science": ["lab_activity", "graphic_organizer", "study_guide", "escape_room", "vocab_cards", "quiz_test", "exit_ticket", "worksheet"],
    "Social Studies": ["escape_room", "scavenger_hunt", "board_game", "study_guide", "graphic_organizer", "crossword", "quiz_test", "reading_comprehension"],
}

DURATION_DAY_COUNTS = {
    "day": 1,
    "week": 5,
    "unit": 15,  # 3 weeks
    "semester": 90,  # 18 weeks
    "year": 180,  # 36 weeks
}

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri"]


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _call_claude(client, model, system, user, max_tokens=4096):
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


def _extract_json(text):
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
    for sc, ec in [("{", "}"), ("[", "]")]:
        start = text.find(sc)
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == sc:
                    depth += 1
                elif text[i] == ec:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break
    return None


def _get_class_info(class_id: str) -> dict:
    """Get class details from DB."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM classes WHERE class_id = %s",
        (class_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else {}


def _get_calendar_week(class_id: str, week_start: date) -> list[dict]:
    """Get curriculum calendar entries for a given week."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    week_end = week_start + timedelta(days=6)
    cur.execute(
        """SELECT * FROM curriculum_calendar
           WHERE class_id = %s
             AND (week_start_date BETWEEN %s AND %s
                  OR week_number = (
                    SELECT week_number FROM curriculum_calendar
                    WHERE class_id = %s AND week_start_date <= %s
                    ORDER BY week_start_date DESC LIMIT 1
                  ))
           ORDER BY week_number ASC""",
        (class_id, week_start, week_end, class_id, week_start),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def _get_standards_for_codes(codes: list[str]) -> list[dict]:
    """Look up full standard descriptions by code."""
    if not codes:
        return []
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    placeholders = ",".join(["%s"] * len(codes))
    cur.execute(
        f"""SELECT s.code, s.description, s.grade_level, s.subject, f.tier, f.name as framework_name
            FROM standards s
            JOIN standards_frameworks f ON s.framework_id = f.framework_id
            WHERE s.code IN ({placeholders}) AND f.is_active = true
            ORDER BY f.priority ASC""",
        codes,
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def run_planner(
    class_id: str,
    teacher_id: str,
    duration_type: str = "week",
    selected_days: list[str] | None = None,
    week_start_date: date | None = None,
    design_theme: str = "modern_clean",
    material_types: list[str] | None = None,
    content_source: str | None = None,
    custom_prompt: str | None = None,
    standards_input: str | None = None,
) -> dict:
    """
    Run the Lesson Planner Agent.

    Args:
        material_types: what the teacher wants generated (worksheet, interactive,
            quiz_test, slides, video, forms). Defaults to templates from SUBJECT_TEMPLATES.
        content_source: 'curriculum' (use current unit), 'standards' (specific codes),
            or 'custom' (free-form prompt). Defaults to 'curriculum'.
        custom_prompt: teacher's description of what to teach (when content_source='custom').
        standards_input: comma-separated standard codes (when content_source='standards').

    Returns a complete plan JSON with daily_plans and work_orders.
    """
    log.info(f"=== Planner: {duration_type} plan for class {class_id} ===")

    client = _get_client()
    class_info = _get_class_info(class_id)
    if not class_info:
        return {"error": "Class not found"}

    subject = class_info.get("subject", "Mathematics")
    grade = class_info.get("grade_level", "4")
    week_start = week_start_date or date.today()
    days = selected_days or DAY_NAMES

    # Filter out non-school days (holidays, PD days, etc.)
    non_school_info = []
    try:
        from src.lms_agents.tools.school_calendar import filter_school_days_for_planner
        filtered_days, non_school = filter_school_days_for_planner(
            teacher_id, week_start, days
        )
        if non_school:
            non_school_info = non_school
            skipped = [ns["day"] for ns in non_school]
            log.info(
                f"[Planner] Filtered out non-school days: {skipped} "
                f"({', '.join(ns.get('label', '') for ns in non_school)})"
            )
            days = filtered_days
        if not days:
            return {
                "error": "No school days in the selected range. All selected days are holidays or non-instructional.",
                "non_school_days": non_school_info,
            }
    except Exception as e:
        log.warning(f"[Planner] School calendar check failed (non-fatal): {e}")

    # Get curriculum calendar for context
    calendar = _get_calendar_week(class_id, week_start)
    calendar_context = ""
    standards_from_calendar = []
    if calendar:
        for entry in calendar:
            calendar_context += f"\nWeek {entry.get('week_number')}: {entry.get('unit_name', '')} — {entry.get('topic', '')}"
            standards_from_calendar.extend(entry.get("standards_scheduled", []))
    else:
        calendar_context = "\nNo curriculum calendar entries for this week."

    # Handle content source — what should the planner teach?
    standards = []  # Initialize to empty list for all paths
    if content_source == 'custom' and custom_prompt:
        # Teacher specified what to teach via free-form prompt
        standards_text = f"TEACHER'S CUSTOM FOCUS: {custom_prompt}"
        standards_from_calendar = []  # Don't use calendar standards
        log.info(f"[Planner] Using custom prompt: {custom_prompt[:80]}...")
    elif content_source == 'standards' and standards_input:
        # Teacher specified specific standard codes
        requested_codes = [c.strip() for c in standards_input.split(',') if c.strip()]
        standards = _get_standards_for_codes(requested_codes)
        standards_text = "\n".join(
            f"- {s['code']}: {s['description']}" for s in standards
        ) if standards else f"Standards requested: {', '.join(requested_codes)}"
        standards_from_calendar = requested_codes
        log.info(f"[Planner] Using teacher-specified standards: {requested_codes}")
    else:
        # Default: use curriculum calendar
        standards = _get_standards_for_codes(standards_from_calendar)
        standards_text = "\n".join(
            f"- {s['code']}: {s['description']}" for s in standards
        ) if standards else "No specific standards scheduled. Use grade-appropriate standards for the subject."

    # Get generation history for exclusion
    history = query_history(teacher_id, standards_from_calendar, freshness_months=6)
    exclusion = build_exclusion_prompt(history)

    # Get analytics feedback for adaptive planning
    analytics_context = ""
    try:
        from src.lms_agents.crews.analytics_crew import get_planner_analytics
        analytics = get_planner_analytics(class_id)
        if analytics.get("struggling_standards") or analytics.get("mastered_standards"):
            analytics_context = "\n\nANALYTICS FEEDBACK (adapt your plan based on this data):\n"
            analytics_context += f"Class Average: {analytics.get('class_average', 'N/A')}%\n"
            if analytics.get("struggling_standards"):
                analytics_context += f"STRUGGLING STANDARDS (need re-teaching): {', '.join(analytics['struggling_standards'])}\n"
            if analytics.get("mastered_standards"):
                analytics_context += f"MASTERED STANDARDS (can skip or advance): {', '.join(analytics['mastered_standards'])}\n"
            if analytics.get("struggling_student_count"):
                analytics_context += f"Students below 65%: {analytics['struggling_student_count']} — suggest accommodation versions\n"
            if analytics.get("recommendations"):
                analytics_context += f"Recommendations: {'; '.join(analytics['recommendations'])}\n"
    except Exception as e:
        log.warning(f"Analytics feedback failed: {e}")

    # Material types — teacher chooses what to generate
    if material_types:
        # Map frontend IDs to template IDs
        material_to_templates = {
            'worksheet': ['worksheet', 'morning_work', 'homework_packet'],
            'interactive': ['interactive'],
            'game': ['game'],
            'quiz_test': ['quiz_test', 'exit_ticket'],
            'slides': ['slides'],
            'video': ['video'],
            'forms': ['forms'],
        }
        available_templates = []
        for mt in material_types:
            available_templates.extend(material_to_templates.get(mt, [mt]))
        # Deduplicate
        available_templates = list(dict.fromkeys(available_templates))
        log.info(f"[Planner] Teacher-selected templates: {available_templates}")
    else:
        # Default: subject-aware templates
        available_templates = SUBJECT_TEMPLATES.get(subject, SUBJECT_TEMPLATES["Mathematics"])

    # Generate Pedagogy Brief for grade-band-appropriate lesson structure
    pedagogy_brief = generate_brief(
        work_order={
            "grade_level": grade,
            "subject": subject,
            "output_template_id": "lesson_plan",
            "question_count": 0,
            "difficulty_distribution": {},
        },
        curriculum_output={"standards": standards, "subject": subject, "grade_level": grade},
        kb_chunks=None,
        class_intel_prompt=None,
        client=client,
    )

    # Narrow the template whitelist to brief-allowed templates if available
    # BUT: if the teacher explicitly selected material_types, those take priority
    # over the brief's recommendations. The brief can only ADD suggestions, not
    # override the teacher's choices.
    teacher_chose_templates = bool(material_types)
    if pedagogy_brief and not teacher_chose_templates:
        ws_formats = (
            pedagogy_brief.get("template_recommendation", {}).get("alternatives") or []
        )
        primary = pedagogy_brief.get("template_recommendation", {}).get("primary")
        if primary:
            ws_formats = [primary] + [t for t in ws_formats if t != primary]
        banned = set(
            pedagogy_brief.get("template_recommendation", {}).get("banned_for_this_task") or []
        )
        if ws_formats:
            available_templates = [t for t in ws_formats if t not in banned]
            log.info(
                f"[Planner] Brief constrained templates to: {available_templates}"
            )
    elif teacher_chose_templates:
        log.info(f"[Planner] Teacher's material choices override brief: {available_templates}")

    brief_section = ""
    if pedagogy_brief:
        brief_section = "\n\n" + format_brief_for_prompt(pedagogy_brief) + "\n"

    system = (
        f"You are an expert lesson planner for grade {grade} {subject}. "
        f"You create engaging, standards-aligned weekly plans that vary templates across days. "
        f"Never use the same template two days in a row. "
        f"Include per-procedure standard citations for every lesson phase. "
        f"When a Pedagogy Brief is provided, the lesson_plan_spec section is AUTHORITATIVE — "
        f"your daily procedures must match its phase structure, durations, transition cadence, "
        f"and manipulatives requirement. Do not exceed total_duration_min."
    )

    user = f"""Create a {duration_type} lesson plan for:

CLASS: {class_info.get('name', 'Class')}
SUBJECT: {subject}
GRADE: {grade}
WEEK START: {week_start.isoformat()}
SELECTED DAYS: {json.dumps(days)}

CURRICULUM CALENDAR:{calendar_context}

STANDARDS TO COVER:
{standards_text}

AVAILABLE TEMPLATES (vary these across days):
{json.dumps(available_templates)}

DESIGN THEME: {design_theme}
{exclusion}
{analytics_context}
{brief_section}

Generate a JSON plan with this structure:
{{
  "rationale": "Brief explanation of the week's learning arc",
  "daily_plans": [
    {{
      "day": "mon",
      "date": "{week_start.isoformat()}",
      "title": "Engaging lesson title",
      "standards": ["code1", "code2"],
      "procedures": [
        {{
          "phase": "Bell Ringer",
          "duration_minutes": 5,
          "description": "What students do",
          "standards_addressed": ["code1"]
        }},
        {{
          "phase": "Direct Instruction",
          "duration_minutes": 15,
          "description": "Teaching activity",
          "standards_addressed": ["code1"]
        }},
        {{
          "phase": "Guided Practice",
          "duration_minutes": 15,
          "description": "Student practice activity",
          "standards_addressed": ["code1", "code2"]
        }},
        {{
          "phase": "Independent Practice",
          "duration_minutes": 10,
          "description": "Assignment work",
          "standards_addressed": ["code2"]
        }},
        {{
          "phase": "Exit Ticket",
          "duration_minutes": 5,
          "description": "Quick assessment",
          "standards_addressed": ["code1"]
        }}
      ],
      "work_orders": [
        {{
          "output_template_id": "worksheet",
          "variant": "worksheet",
          "question_count": 10,
          "standards_ids": ["code1", "code2"],
          "difficulty_distribution": {{"easy": 3, "medium": 4, "hard": 3}},
          "config": {{"question_count": 10, "include_answer_key": true}},
          "accommodations": [],
          "confirmed": false
        }}
      ]
    }}
  ]
}}

IMPORTANT:
- Create plans for each of these days: {json.dumps(days)}
- USE ONLY the templates from the AVAILABLE TEMPLATES list above for work_orders.
  The teacher specifically chose these material types — do NOT substitute others.
  Distribute different template types across days so the week has variety.
  For example, if the teacher chose worksheet + slides + video + interactive + forms,
  assign one different type per day (Mon=worksheet, Tue=slides, Wed=video, Thu=interactive, Fri=forms).
- Include the procedure phases that match the Pedagogy Brief lesson_plan_spec when provided
  (K-2 will be ~25-30 min with hook → mini-lesson → guided → movement break → independent → share;
   secondary will be longer with bell ringer → direct → guided → independent → exit ticket).
  Use realistic time allocations.
- Every procedure phase must have standards_addressed
- Each day should have 1 work_order using a template from the AVAILABLE TEMPLATES list
- Make titles engaging and specific (not generic "Math Lesson")
- Date each day correctly starting from {week_start.isoformat()}
- Every work_order MUST include: "variant" (a sensible default matching the template),
  "config" (a small dict of starting values — e.g. question_count, or for slides an
  "outline" list of 5-7 slide titles, or for forms a "questions" list of 5 question stems),
  "accommodations": [] (always empty; teacher ticks these in the UI), and "confirmed": false.
  These fields are used by the teacher's refinement step before generation.
- If a Pedagogy Brief was provided above, every constraint is mandatory:
  template choice, phase durations, transition cadence, scaffolds, vocabulary
  caps, and assessment modes must ALL be honored

Respond with ONLY the JSON object."""

    response = _call_claude(client, SONNET, system, user, max_tokens=8192)
    plan_data = _extract_json(response)

    if not plan_data:
        log.warning("[Planner] Failed to parse plan JSON")
        plan_data = {"rationale": "Plan generation incomplete", "daily_plans": []}

    # Persist grade, subject, and the pedagogy brief on the plan so downstream
    # assignment generation can use them (fixes hardcoded grade=4 bug).
    plan_data["grade_level"] = grade
    plan_data["subject"] = subject
    plan_data["pedagogy_brief"] = pedagogy_brief
    plan_data["pedagogy_pack_id"] = (pedagogy_brief or {}).get("_pack_id")

    # Store plan in database
    plan_id = _store_plan(
        class_id=class_id,
        teacher_id=teacher_id,
        duration_type=duration_type,
        selected_days=days,
        week_start=week_start,
        plan_data=plan_data,
    )

    plan_data["plan_id"] = plan_id
    plan_data["duration_type"] = duration_type
    plan_data["week_start_date"] = week_start.isoformat()
    plan_data["class_id"] = class_id
    plan_data["status"] = "suggested"

    total_wo = sum(len(dp.get("work_orders", [])) for dp in plan_data.get("daily_plans", []))
    log.info(f"[Planner] Plan created: {len(plan_data.get('daily_plans', []))} days, {total_wo} work orders")
    return plan_data


def _store_plan(
    class_id: str, teacher_id: str, duration_type: str,
    selected_days: list, week_start: date, plan_data: dict,
) -> str:
    """Store a plan in the lesson_plans table."""
    conn = get_connection()
    cur = conn.cursor()
    plan_id = str(uuid4())
    try:
        cur.execute(
            """INSERT INTO lesson_plans
               (plan_id, class_id, teacher_id, duration_type, selected_days,
                week_start_date, status, plan_data)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, 'suggested', %s)""",
            (plan_id, class_id, teacher_id, duration_type, Json(selected_days),
             week_start, Json(plan_data)),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to store plan: {e}")
    finally:
        cur.close()
        conn.close()
    return plan_id


def _dispatch_secondary(
    template: str,
    assignment_id: str,
    teacher_id: str,
    class_id: str,
    subject: str,
    grade: str,
    wo: dict,
) -> dict:
    """
    Dispatch a secondary generation step after the base assignment is created.

    Each material type gets routed to its correct crew/generator. All secondary
    steps are non-fatal — if they fail, the base assignment still exists and
    the entry gets marked with the error.
    """
    log.info(f"[Dispatcher] Secondary dispatch: {template} for assignment {assignment_id}")

    try:
        if template == "video":
            from src.lms_agents.crews.video_crew import generate_video
            _cfg = (wo or {}).get("config") or {}
            video_result = generate_video(
                assignment_id=assignment_id,
                teacher_id=teacher_id,
                target_duration=_cfg.get("target_length_sec") or 240,
                theme="modern_clean",
                subject_override=subject,
                grade_override=grade,
                topic_override=_cfg.get("topic"),
            )
            if video_result.get("error"):
                return {"secondary_status": "failed", "secondary_error": video_result["error"]}
            return {
                "secondary_status": "complete",
                "secondary_type": "video",
                "video_id": video_result.get("video_id"),
                "video_url": video_result.get("file_url"),
                "duration_seconds": video_result.get("duration_seconds"),
            }

        elif template == "interactive":
            from src.lms_agents.tools.interactive_generator import generate_interactive_activity
            # Honor teacher's refinement: activity_type override
            _cfg = (wo or {}).get("config") or {}
            interactive_template_id = _cfg.get("activity_type") or "multiple_choice_quiz"
            interactive_result = generate_interactive_activity(
                assignment_id=assignment_id,
                teacher_id=teacher_id,
                interactive_template_id=interactive_template_id,
                class_id=class_id,
            )
            if interactive_result.get("error"):
                return {"secondary_status": "failed", "secondary_error": interactive_result["error"]}
            return {
                "secondary_status": "complete",
                "secondary_type": "interactive",
                "activity_id": interactive_result.get("activity_id"),
                "access_code": interactive_result.get("access_code"),
                "access_url": interactive_result.get("access_url"),
            }

        elif template == "game":
            from src.lms_agents.tools.game_session_manager import create_game_session
            game_result = create_game_session(
                teacher_id=teacher_id,
                assignment_id=assignment_id,
                game_shell_id="classic_quiz",
            )
            if game_result.get("error"):
                return {"secondary_status": "failed", "secondary_error": game_result["error"]}
            return {
                "secondary_status": "complete",
                "secondary_type": "game",
                "game_pin": game_result.get("pin"),
                "session_id": game_result.get("session_id"),
            }

        elif template == "slides":
            from src.lms_agents.tools.gemini_slides import generate_slide_content, create_google_slides
            from src.lms_agents.tools.db import get_connection as _gc
            from psycopg2.extras import RealDictCursor as _RDC
            # Get assignment content for slide generation
            conn = _gc()
            cur = conn.cursor(cursor_factory=_RDC)
            cur.execute("SELECT title, questions, standards_ids FROM assignments WHERE assignment_id = %s", (assignment_id,))
            asgn = cur.fetchone()
            cur.close()
            conn.close()
            if not asgn:
                return {"secondary_status": "failed", "secondary_error": "Assignment not found for slides"}

            content = {"title": asgn["title"], "questions": asgn["questions"] or []}
            standards = asgn.get("standards_ids") or []
            # If teacher refined a slide outline, use it directly instead of auto-generating
            _cfg = (wo or {}).get("config") or {}
            teacher_outline = _cfg.get("outline")
            if teacher_outline:
                slides_content = [
                    {"title": s.get("title", ""), "bullets": s.get("bullets", []), "layout": _cfg.get("layout_style", "lecture")}
                    for s in teacher_outline
                ]
            else:
                slides_content = generate_slide_content(content, standards)

            try:
                slides_result = create_google_slides(teacher_id, slides_content, asgn["title"])
                return {
                    "secondary_status": "complete",
                    "secondary_type": "slides",
                    "slides_url": slides_result.get("url"),
                    "slides_id": slides_result.get("presentation_id"),
                }
            except Exception as oauth_err:
                # OAuth not connected — return the slide content without the Google API call
                return {
                    "secondary_status": "partial",
                    "secondary_type": "slides",
                    "secondary_note": f"Slide content generated but Google OAuth not connected: {oauth_err}",
                    "slides_content": slides_content[:3],  # First 3 slides as preview
                }

        elif template == "forms":
            from src.lms_agents.tools.google_forms import create_quiz_form
            from src.lms_agents.tools.db import get_connection as _gc
            from psycopg2.extras import RealDictCursor as _RDC
            conn = _gc()
            cur = conn.cursor(cursor_factory=_RDC)
            cur.execute("SELECT title, questions FROM assignments WHERE assignment_id = %s", (assignment_id,))
            asgn = cur.fetchone()
            cur.close()
            conn.close()
            if not asgn:
                return {"secondary_status": "failed", "secondary_error": "Assignment not found for forms"}

            _cfg = (wo or {}).get("config") or {}
            teacher_questions = _cfg.get("questions")
            form_questions = teacher_questions if teacher_questions else (asgn["questions"] or [])
            try:
                form_result = create_quiz_form(
                    teacher_id=teacher_id,
                    title=asgn["title"],
                    questions=form_questions,
                )
                return {
                    "secondary_status": "complete",
                    "secondary_type": "forms",
                    "form_url": form_result.get("form_url"),
                    "form_id": form_result.get("form_id"),
                }
            except Exception as oauth_err:
                return {
                    "secondary_status": "partial",
                    "secondary_type": "forms",
                    "secondary_note": f"Quiz content generated but Google OAuth not connected: {oauth_err}",
                }

        else:
            return {"secondary_status": "skipped", "secondary_note": f"Unknown secondary type: {template}"}

    except Exception as e:
        log.error(f"[Dispatcher] Secondary dispatch failed for {template}: {e}")
        return {"secondary_status": "failed", "secondary_error": str(e)}


def _update_plan_progress(plan_id: str, assignments: list[dict], total_work_orders: int) -> None:
    """Write generation progress to the lesson_plans table so the frontend can poll it."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        progress = {
            "completed": len(assignments),
            "total": total_work_orders,
            "assignments": assignments,
        }
        cur.execute(
            """UPDATE lesson_plans
               SET plan_data = jsonb_set(
                   plan_data,
                   '{generation_progress}',
                   %s::jsonb
               )
               WHERE plan_id = %s""",
            (json.dumps(progress), plan_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.warning(f"[Planner] Progress update failed: {e}")
    finally:
        cur.close()
        conn.close()


def approve_plan(plan_id: str, sync_to_classroom: bool = False) -> dict:
    """
    Approve a plan and generate all work_orders.

    If sync_to_classroom=True and the class has a google_classroom_course_id,
    each generated assignment is also posted to Google Classroom.

    Returns dict with plan_id and list of generated assignment_ids.
    """
    from src.lms_agents.crews.assignment_crew import run_assignment_crew

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM lesson_plans WHERE plan_id = %s", (plan_id,))
    plan = cur.fetchone()
    cur.close()
    conn.close()

    if not plan:
        return {"error": "Plan not found"}

    plan_data = plan["plan_data"]
    teacher_id = str(plan["teacher_id"])
    class_id = str(plan["class_id"])

    # Pull grade and subject from the plan_data we persisted at planning time.
    # Falls back to the class record if the plan was created before this fix.
    plan_grade = plan_data.get("grade_level")
    plan_subject = plan_data.get("subject")
    if not plan_grade or not plan_subject:
        class_info = _get_class_info(class_id)
        plan_grade = plan_grade or class_info.get("grade_level") or "4"
        plan_subject = plan_subject or class_info.get("subject") or "Mathematics"

    # Update status to generating
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE lesson_plans SET status = 'generating', approved_at = NOW() WHERE plan_id = %s",
        (plan_id,),
    )
    conn.commit()
    cur.close()
    conn.close()

    # Check Google Classroom connection for this class
    classroom_course_id = None
    if sync_to_classroom:
        try:
            gc_conn = get_connection()
            gc_cur = gc_conn.cursor()
            gc_cur.execute(
                "SELECT google_classroom_course_id FROM classes WHERE class_id = %s",
                (class_id,),
            )
            gc_row = gc_cur.fetchone()
            classroom_course_id = gc_row[0] if gc_row and gc_row[0] else None
            gc_cur.close()
            gc_conn.close()
            if classroom_course_id:
                log.info(f"[Planner] Classroom sync enabled: course_id={classroom_course_id}")
            else:
                log.info("[Planner] Classroom sync requested but no course_id linked")
        except Exception as e:
            log.warning(f"[Planner] Classroom lookup failed: {e}")

    # Count total work orders for progress tracking
    total_work_orders = sum(
        len(dp.get("work_orders", [])) for dp in plan_data.get("daily_plans", [])
    )

    # ── Material Type Dispatcher ──
    # Routes each work_order to the correct generation crew based on template type.
    #
    # Most material types need a base assignment first (content + questions),
    # then a secondary conversion step:
    #   worksheet/quiz/exit_ticket → Assignment Crew only (done)
    #   video → Assignment Crew (base content) → Video Crew (script + TTS + render)
    #   interactive → Assignment Crew (base content) → Interactive Generator (React app)
    #   game → Assignment Crew (base content) → Game Session Manager (WebSocket game)
    #   slides → Assignment Crew (base content) → Gemini Slides (Google Slides API)
    #   forms → Assignment Crew (base content) → Google Forms (Forms API)

    # Templates that only need the Assignment Crew
    ASSIGNMENT_ONLY_TEMPLATES = {
        "worksheet", "task_cards", "exit_ticket", "quiz_test", "morning_work",
        "homework_packet", "flashcards", "bingo", "word_search", "crossword",
        "board_game", "scavenger_hunt", "escape_room", "vocab_cards",
        "anchor_chart", "study_guide", "reading_comprehension",
        "graphic_organizer", "lab_activity", "lab_report", "writing_prompts",
        "sub_plans", "parent_newsletter",
        # Science variants (refinement)
        "lab_procedure", "observation_journal", "data_table", "cer_writing_frame",
        "vocabulary_cards",
    }

    # Map the 4 frontend accommodation IDs to the engine's DEFAULT_PROFILES keys
    ACCOMMODATION_PROFILE_MAP = {
        "iep_reduced": "iep_reading_reduced",
        "504_extended": "504_extended_time",
        "ell_beginner": "ell_beginner",
        "gifted_enriched": "gifted_enriched",
    }

    # Templates that need Assignment Crew THEN a secondary step
    SECONDARY_DISPATCH = {
        "video": "_dispatch_video",
        "interactive": "_dispatch_interactive",
        "game": "_dispatch_game",
        "slides": "_dispatch_slides",
        "forms": "_dispatch_forms",
    }

    assignment_ids = []
    daily_plans = plan_data.get("daily_plans", [])

    for dp in daily_plans:
        day = dp.get("day", "")
        day_date = dp.get("date", "")
        for i, wo in enumerate(dp.get("work_orders", [])):
            template = wo.get("output_template_id", "worksheet")
            variant = wo.get("variant")
            wo_config = wo.get("config") or {}
            wo_accommodations = wo.get("accommodations") or []
            # If teacher chose a worksheet variant via refinement, use it as the template
            effective_template = variant if (variant and variant in ASSIGNMENT_ONLY_TEMPLATES) else (
                template if template in ASSIGNMENT_ONLY_TEMPLATES else "worksheet"
            )
            work_order = {
                "work_order_id": f"WO-{plan_id[:8]}-{day}-{i+1:02d}",
                "class_id": class_id,
                "teacher_id": teacher_id,
                "output_template_id": effective_template,
                "output_format": wo.get("output_format", "html"),
                "design_theme": wo.get("design_theme", "modern_clean"),
                "subject": plan_subject,
                "grade_level": plan_grade,
                "standards_ids": wo.get("standards_ids", []),
                "question_count": wo_config.get("question_count", wo.get("question_count", 10)),
                "difficulty_distribution": wo.get("difficulty_distribution", {"easy": 3, "medium": 4, "hard": 3}),
                "has_kb_coverage": True,
                # Pass refinement extras through so downstream crews can honor them
                "variant": variant,
                "refinement_config": wo_config,
            }

            try:
                # Phase 1: Always generate base assignment (content + questions)
                result = run_assignment_crew(work_order)
                assignment_id = result.get("assignment_id")
                a_entry = {
                    "day": day,
                    "assignment_id": assignment_id,
                    "title": result.get("title"),
                    "template": template,
                    "status": "complete",
                }

                # Phase 2: If this is a secondary material type, dispatch to the right crew
                if template in SECONDARY_DISPATCH and assignment_id:
                    secondary_result = _dispatch_secondary(
                        template, assignment_id, teacher_id, class_id,
                        plan_subject, plan_grade, wo
                    )
                    a_entry.update(secondary_result)

                # Phase 3: Generate accommodation versions (if teacher ticked any)
                if wo_accommodations and assignment_id:
                    from src.lms_agents.tools.accommodation_engine import (
                        get_profile as _get_profile,
                        apply_modifications as _apply_mods,
                    )
                    accommodation_versions = []
                    for accom_id in wo_accommodations:
                        profile_id = ACCOMMODATION_PROFILE_MAP.get(accom_id, accom_id)
                        profile = _get_profile(profile_id, teacher_id)
                        if not profile:
                            log.warning(f"[Accom] Unknown profile {accom_id} ({profile_id})")
                            continue
                        try:
                            if template == "forms":
                                # For Forms: generate a parallel Form with modified questions
                                from src.lms_agents.tools.google_forms import create_quiz_form
                                from src.lms_agents.tools.db import get_connection as _gc
                                from psycopg2.extras import RealDictCursor as _RDC
                                _conn = _gc()
                                _cur = _conn.cursor(cursor_factory=_RDC)
                                _cur.execute(
                                    "SELECT title, questions FROM assignments WHERE assignment_id = %s",
                                    (assignment_id,),
                                )
                                base_asgn = _cur.fetchone()
                                _cur.close(); _conn.close()
                                if base_asgn:
                                    modified = _apply_mods(
                                        {"title": base_asgn["title"], "questions": base_asgn["questions"] or []},
                                        profile, plan_subject, plan_grade,
                                    )
                                    try:
                                        form_res = create_quiz_form(
                                            teacher_id=teacher_id,
                                            title=f"{base_asgn['title']} — {profile['name']}",
                                            questions=modified.get("questions", []),
                                        )
                                        accommodation_versions.append({
                                            "accommodation_id": accom_id,
                                            "profile_name": profile["name"],
                                            "form_url": form_res.get("form_url"),
                                            "form_id": form_res.get("form_id"),
                                            "status": "complete",
                                        })
                                    except Exception as oe:
                                        accommodation_versions.append({
                                            "accommodation_id": accom_id,
                                            "profile_name": profile["name"],
                                            "status": "partial",
                                            "note": f"Modified content generated but Forms OAuth not connected: {oe}",
                                        })
                            else:
                                # For everything else: Claude regenerates content with modifications
                                from src.lms_agents.tools.db import get_connection as _gc
                                from psycopg2.extras import RealDictCursor as _RDC
                                _conn = _gc()
                                _cur = _conn.cursor(cursor_factory=_RDC)
                                _cur.execute(
                                    "SELECT title, questions FROM assignments WHERE assignment_id = %s",
                                    (assignment_id,),
                                )
                                base_asgn = _cur.fetchone()
                                _cur.close(); _conn.close()
                                if base_asgn:
                                    modified = _apply_mods(
                                        {"title": base_asgn["title"], "questions": base_asgn["questions"] or []},
                                        profile, plan_subject, plan_grade,
                                    )
                                    accommodation_versions.append({
                                        "accommodation_id": accom_id,
                                        "profile_name": profile["name"],
                                        "modified_content": modified,
                                        "status": "complete",
                                    })
                        except Exception as ae:
                            log.error(f"[Accom] Generation failed for {accom_id}: {ae}")
                            accommodation_versions.append({
                                "accommodation_id": accom_id,
                                "status": "failed",
                                "error": str(ae),
                            })
                    if accommodation_versions:
                        a_entry["accommodation_versions"] = accommodation_versions

                # Google Classroom sync (if requested and connected)
                if sync_to_classroom and classroom_course_id and assignment_id:
                    try:
                        from src.lms_agents.tools.google_classroom import push_assignment_to_classroom
                        gc_result = push_assignment_to_classroom(
                            teacher_id=teacher_id,
                            course_id=classroom_course_id,
                            title=result.get("title", template),
                            description=f"Auto-generated {template} for {day}",
                            assignment_id=assignment_id,
                        )
                        a_entry["classroom_synced"] = True
                        a_entry["classroom_url"] = gc_result.get("alternateLink")
                        log.info(f"[Planner] Synced to Classroom: {result.get('title')}")
                    except Exception as gc_err:
                        a_entry["classroom_synced"] = False
                        a_entry["classroom_error"] = str(gc_err)
                        log.warning(f"[Planner] Classroom sync failed (non-fatal): {gc_err}")

                assignment_ids.append(a_entry)
                _update_plan_progress(plan_id, assignment_ids, total_work_orders)
            except Exception as e:
                log.error(f"Failed to generate {work_order['work_order_id']}: {e}")
                assignment_ids.append({
                    "day": day,
                    "assignment_id": None,
                    "template": template,
                    "status": "failed",
                    "error": str(e),
                })
                _update_plan_progress(plan_id, assignment_ids, total_work_orders)

    # Update plan status
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE lesson_plans SET status = 'complete' WHERE plan_id = %s",
        (plan_id,),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        "plan_id": plan_id,
        "status": "complete",
        "assignments": assignment_ids,
        "total_generated": sum(1 for a in assignment_ids if a["status"] == "complete"),
    }
