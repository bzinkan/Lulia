"""
Seed Demo Data — populates a fresh Lulia install with realistic test data.

Run: docker compose exec api python scripts/seed_demo_data.py

Creates:
  - 1 demo teacher
  - 2 classes (4th Math, 5th Science)
  - Curriculum calendar (4 weeks)
  - 5 sample assignments (different templates)
  - Sample submissions with grades
  - Analytics data
  - Accommodation profiles
"""
import json
import logging
import os
import sys
from datetime import date, timedelta
from uuid import uuid4

sys.path.insert(0, "/app")

import psycopg2
from psycopg2.extras import Json

logging.basicConfig(level=logging.INFO, format="%(asctime)s [seed] %(message)s")
log = logging.getLogger(__name__)

TEACHER_ID = "00000000-0000-0000-0000-000000000001"
CLASS_MATH = "00000000-0000-0000-0000-000000000010"
CLASS_SCI = "00000000-0000-0000-0000-000000000020"


def get_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )


def seed():
    conn = get_db()
    cur = conn.cursor()
    log.info("=== Seeding Demo Data ===")

    # Teacher
    cur.execute("""
        UPDATE teachers SET name = 'Sarah Johnson', state_code = 'OH', design_theme = 'modern_clean',
        onboarding_complete = true, credit_balance = 200, tier = 'plus'
        WHERE teacher_id = %s
    """, (TEACHER_ID,))
    log.info("  Teacher: Sarah Johnson (demo@lulia.com)")

    # Classes
    cur.execute("""
        INSERT INTO classes (class_id, teacher_id, name, subject, grade_level, school_year, period)
        VALUES (%s, %s, '4th Grade Math - Period 1', 'Mathematics', '4', '2026-2027', '1')
        ON CONFLICT DO NOTHING
    """, (CLASS_MATH, TEACHER_ID))
    cur.execute("""
        INSERT INTO classes (class_id, teacher_id, name, subject, grade_level, school_year, period)
        VALUES (%s, %s, '5th Grade Science - Period 3', 'Science', '5', '2026-2027', '3')
        ON CONFLICT DO NOTHING
    """, (CLASS_SCI, TEACHER_ID))
    log.info("  Classes: 4th Math, 5th Science")

    # Calendar (4 weeks)
    monday = date.today() - timedelta(days=date.today().weekday())
    for week in range(4):
        ws = monday + timedelta(weeks=week)
        topics = [
            ("Unit 1: Fractions", "Equivalent Fractions", ["4.NF.1", "4.NF.2"]),
            ("Unit 1: Fractions", "Adding Fractions", ["4.NF.3"]),
            ("Unit 2: Decimals", "Decimal Notation", ["4.NF.5", "4.NF.6"]),
            ("Unit 2: Decimals", "Comparing Decimals", ["4.NF.7"]),
        ][week]
        cur.execute("""
            INSERT INTO curriculum_calendar (calendar_id, class_id, week_number, week_start_date, unit_name, topic, standards_scheduled, is_assessment_week)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (str(uuid4()), CLASS_MATH, week + 1, ws, topics[0], topics[1], Json(topics[2]), week == 3))
    log.info("  Calendar: 4 weeks seeded")

    # Assignments (5 different templates)
    templates = [
        ("Equivalent Fractions Practice", "worksheet", ["4.NF.1"]),
        ("Fraction Bingo", "bingo", ["4.NF.1", "4.NF.2"]),
        ("Adding Fractions Task Cards", "task_cards", ["4.NF.3"]),
        ("Fractions Exit Ticket", "exit_ticket", ["4.NF.1"]),
        ("Decimal Word Search", "word_search", ["4.NF.5"]),
    ]
    assignment_ids = []
    for i, (title, tmpl, stds) in enumerate(templates):
        aid = str(uuid4())
        assignment_ids.append(aid)
        questions = [{"question_number": j+1, "question_text": f"Sample Q{j+1} for {title}", "answer": f"Answer {j+1}", "difficulty": ["easy", "medium", "hard"][j % 3], "standard_code": stds[0]} for j in range(6)]
        cur.execute("""
            INSERT INTO assignments (assignment_id, class_id, teacher_id, title, output_template_id, output_format, design_theme, standards_ids, questions, status, assigned_date)
            VALUES (%s, %s, %s, %s, %s, 'html', 'modern_clean', %s, %s, 'complete', %s)
            ON CONFLICT DO NOTHING
        """, (aid, CLASS_MATH, TEACHER_ID, title, tmpl, Json(stds), Json(questions), monday + timedelta(days=i)))
    log.info(f"  Assignments: {len(templates)} created")

    # Submissions + Grades
    students = [("Alice Chen", "00000000-0000-0000-0000-000000000091"),
                ("Brian Kim", "00000000-0000-0000-0000-000000000092"),
                ("Carlos Lopez", "00000000-0000-0000-0000-000000000093")]
    for aid in assignment_ids[:2]:
        for name, sid in students:
            sub_id = str(uuid4())
            cur.execute("""
                INSERT INTO submissions (submission_id, assignment_id, student_id, student_name, submission_method, status)
                VALUES (%s, %s::uuid, %s::uuid, %s, 'digital', 'graded') ON CONFLICT DO NOTHING
            """, (sub_id, aid, sid, name))
            for qn in range(1, 7):
                pts = 1.0 if qn <= 4 else 0.5
                cur.execute("""
                    INSERT INTO grades (grade_id, submission_id, question_number, student_response, correct_answer, points_earned, points_possible, feedback, needs_review)
                    VALUES (%s, %s, %s, 'response', 'answer', %s, 1.0, 'Auto-graded', false) ON CONFLICT DO NOTHING
                """, (str(uuid4()), sub_id, qn, pts))
    log.info("  Submissions: 6 graded (3 students × 2 assignments)")

    # Student Mastery
    for name, sid in students:
        for std in ["4.NF.1", "4.NF.2"]:
            correct = 4 if name == "Alice Chen" else 3 if name == "Brian Kim" else 2
            pct = round(correct / 6 * 100, 1)
            cur.execute("""
                INSERT INTO student_mastery (mastery_id, student_id, standard_id, total_questions, correct_questions, mastery_percentage, trend)
                VALUES (%s, %s::uuid, %s, 6, %s, %s, 'stable') ON CONFLICT DO NOTHING
            """, (str(uuid4()), sid, std, correct, pct))
    log.info("  Mastery: 6 records")

    # Lesson Plan
    plan_id = str(uuid4())
    cur.execute("""
        INSERT INTO lesson_plans (plan_id, class_id, teacher_id, duration_type, week_start_date, status, plan_data)
        VALUES (%s, %s::uuid, %s::uuid, 'week', %s, 'complete', %s) ON CONFLICT DO NOTHING
    """, (plan_id, CLASS_MATH, TEACHER_ID, monday, Json({"rationale": "Demo plan", "daily_plans": []})))
    log.info("  Lesson plan: 1 complete")

    conn.commit()
    cur.close()
    conn.close()

    log.info("\n=== Demo Data Complete ===")
    log.info("  Login: demo@lulia.com")
    log.info("  Tier: Plus (200 credits)")
    log.info("  Classes: 2")
    log.info("  Assignments: 5")
    log.info("  Students: 3 with grades")


if __name__ == "__main__":
    seed()
