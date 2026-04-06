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
) -> dict:
    """
    Run the Lesson Planner Agent.

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

    # Get full standard descriptions
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

    # Subject-aware templates
    available_templates = SUBJECT_TEMPLATES.get(subject, SUBJECT_TEMPLATES["Mathematics"])

    system = (
        f"You are an expert lesson planner for grade {grade} {subject}. "
        f"You create engaging, standards-aligned weekly plans that vary templates across days. "
        f"Never use the same template two days in a row. "
        f"Include per-procedure standard citations for every lesson phase."
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
          "question_count": 10,
          "standards_ids": ["code1", "code2"],
          "difficulty_distribution": {{"easy": 3, "medium": 4, "hard": 3}}
        }}
      ]
    }}
  ]
}}

IMPORTANT:
- Create plans for each of these days: {json.dumps(days)}
- Vary templates across days (use at least 3 different templates for a full week)
- Include 4-5 procedure phases per day with realistic time allocations
- Every procedure phase must have standards_addressed
- Each day should have 1-2 work_orders for materials to generate
- Make titles engaging and specific (not generic "Math Lesson")
- Date each day correctly starting from {week_start.isoformat()}

Respond with ONLY the JSON object."""

    response = _call_claude(client, SONNET, system, user, max_tokens=8192)
    plan_data = _extract_json(response)

    if not plan_data:
        log.warning("[Planner] Failed to parse plan JSON")
        plan_data = {"rationale": "Plan generation incomplete", "daily_plans": []}

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


def approve_plan(plan_id: str) -> dict:
    """
    Approve a plan and generate all work_orders.

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

    # Generate each work order
    assignment_ids = []
    daily_plans = plan_data.get("daily_plans", [])

    for dp in daily_plans:
        day = dp.get("day", "")
        day_date = dp.get("date", "")
        for i, wo in enumerate(dp.get("work_orders", [])):
            work_order = {
                "work_order_id": f"WO-{plan_id[:8]}-{day}-{i+1:02d}",
                "class_id": class_id,
                "teacher_id": teacher_id,
                "output_template_id": wo.get("output_template_id", "worksheet"),
                "output_format": wo.get("output_format", "html"),
                "design_theme": wo.get("design_theme", "modern_clean"),
                "subject": plan.get("plan_data", {}).get("subject", "Mathematics"),
                "grade_level": "4",
                "standards_ids": wo.get("standards_ids", []),
                "question_count": wo.get("question_count", 10),
                "difficulty_distribution": wo.get("difficulty_distribution", {"easy": 3, "medium": 4, "hard": 3}),
                "has_kb_coverage": True,
            }
            try:
                result = run_assignment_crew(work_order)
                assignment_ids.append({
                    "day": day,
                    "assignment_id": result.get("assignment_id"),
                    "title": result.get("title"),
                    "template": wo.get("output_template_id"),
                    "status": "complete",
                })
            except Exception as e:
                log.error(f"Failed to generate {work_order['work_order_id']}: {e}")
                assignment_ids.append({
                    "day": day,
                    "assignment_id": None,
                    "template": wo.get("output_template_id"),
                    "status": "failed",
                    "error": str(e),
                })

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
