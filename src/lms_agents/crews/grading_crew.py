"""
Scan & Grade Crew — processes submissions and grades them.

Chain: Intake → OCR → Confidence Check → Grading → Report
Supports: phone scan, upload scan, digital quiz, manual entry
"""
import json
import logging
import os
from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection
from src.lms_agents.tools.answer_matcher import grade_question
from src.lms_agents.tools.ocr_processor import process_image_with_vision

log = logging.getLogger(__name__)


def _get_assignment(assignment_id: str) -> dict | None:
    """Fetch assignment with questions and answer key."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM assignments WHERE assignment_id = %s", (assignment_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def _store_submission(
    assignment_id: str, student_id: str | None, student_name: str | None,
    method: str, raw_file_url: str | None, ocr_responses: dict | None,
    confidence: dict | None, flagged: list | None, status: str,
) -> str:
    """Store a submission record."""
    conn = get_connection()
    cur = conn.cursor()
    submission_id = str(uuid4())
    cur.execute(
        """INSERT INTO submissions
           (submission_id, assignment_id, student_id, student_name,
            submission_method, raw_file_url, ocr_responses, confidence_scores,
            flagged_questions, status)
           VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (submission_id, assignment_id, student_id, student_name,
         method, raw_file_url, Json(ocr_responses or {}),
         Json(confidence or {}), Json(flagged or []), status),
    )
    conn.commit()
    cur.close()
    conn.close()
    return submission_id


def _store_grades(submission_id: str, grades_list: list[dict]):
    """Store individual question grades."""
    conn = get_connection()
    cur = conn.cursor()
    for g in grades_list:
        cur.execute(
            """INSERT INTO grades
               (grade_id, submission_id, question_number, student_response,
                correct_answer, points_earned, points_possible, feedback,
                needs_review, teacher_override)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, false)""",
            (str(uuid4()), submission_id, g["question_number"],
             g.get("student_response", ""), g.get("correct_answer", ""),
             g["points_earned"], g["points_possible"],
             g.get("feedback", ""), g.get("needs_review", False)),
        )
    conn.commit()
    cur.close()
    conn.close()


def _update_mastery(student_id: str | None, grades_list: list[dict], questions: list[dict]):
    """Update student_mastery table with grading results."""
    if not student_id:
        return
    # Group grades by standard
    by_standard: dict[str, dict] = {}
    for g in grades_list:
        qnum = g["question_number"]
        # Find the standard for this question
        for q in questions:
            if q.get("question_number") == qnum:
                std = q.get("standard_code", "")
                if std:
                    if std not in by_standard:
                        by_standard[std] = {"total": 0, "correct": 0}
                    by_standard[std]["total"] += 1
                    if g.get("points_earned", 0) >= g.get("points_possible", 1) * 0.7:
                        by_standard[std]["correct"] += 1
                break

    conn = get_connection()
    cur = conn.cursor()
    for std, data in by_standard.items():
        pct = round(data["correct"] / max(data["total"], 1) * 100, 1)
        cur.execute(
            """INSERT INTO student_mastery
               (mastery_id, student_id, standard_id, total_questions,
                correct_questions, mastery_percentage, trend)
               VALUES (%s, %s::uuid, %s, %s, %s, %s, 'stable')""",
            (str(uuid4()), student_id, std, data["total"], data["correct"], pct),
        )
    conn.commit()
    cur.close()
    conn.close()


def grade_scan_submission(
    assignment_id: str,
    image_bytes: bytes,
    student_id: str | None = None,
    student_name: str | None = None,
    file_url: str | None = None,
) -> dict:
    """
    Full grading pipeline for a scanned image submission.
    Intake → OCR → Confidence → Grade → Store
    """
    log.info(f"[Grading] Processing scan for assignment {assignment_id}")

    # Intake: get assignment and answer key
    assignment = _get_assignment(assignment_id)
    if not assignment:
        return {"error": "Assignment not found"}

    questions = assignment.get("questions", [])
    answer_key_data = assignment.get("answer_key", {})
    ak_items = answer_key_data.get("answer_key", []) if isinstance(answer_key_data, dict) else []

    # OCR: extract responses using vision
    ocr_result = process_image_with_vision(image_bytes, questions)
    responses = ocr_result.get("responses", {})
    confidence = ocr_result.get("confidence", {})
    flagged = ocr_result.get("flagged", [])
    detected_name = ocr_result.get("student_name") or student_name

    # Grade each question
    grades_list = _grade_responses(responses, questions, ak_items, confidence)

    # Determine status
    status = "needs_review" if flagged else "graded"

    # Store
    submission_id = _store_submission(
        assignment_id, student_id, detected_name, "phone_scan",
        file_url, responses, confidence, flagged, status,
    )
    _store_grades(submission_id, grades_list)
    _update_mastery(student_id, grades_list, questions)

    total_earned = sum(g["points_earned"] for g in grades_list)
    total_possible = sum(g["points_possible"] for g in grades_list)

    return {
        "submission_id": submission_id,
        "student_name": detected_name,
        "status": status,
        "total_earned": round(total_earned, 1),
        "total_possible": round(total_possible, 1),
        "percentage": round(total_earned / max(total_possible, 1) * 100, 1),
        "grades": grades_list,
        "flagged_questions": flagged,
        "ocr_confidence": confidence,
    }


def grade_digital_submission(
    assignment_id: str,
    responses: dict,
    student_id: str | None = None,
    student_name: str | None = None,
) -> dict:
    """Grade a digital quiz submission (responses already extracted)."""
    log.info(f"[Grading] Processing digital submission for assignment {assignment_id}")

    assignment = _get_assignment(assignment_id)
    if not assignment:
        return {"error": "Assignment not found"}

    questions = assignment.get("questions", [])
    answer_key_data = assignment.get("answer_key", {})
    ak_items = answer_key_data.get("answer_key", []) if isinstance(answer_key_data, dict) else []

    grades_list = _grade_responses(responses, questions, ak_items)

    submission_id = _store_submission(
        assignment_id, student_id, student_name, "digital",
        None, responses, None, None, "graded",
    )
    _store_grades(submission_id, grades_list)
    _update_mastery(student_id, grades_list, questions)

    total_earned = sum(g["points_earned"] for g in grades_list)
    total_possible = sum(g["points_possible"] for g in grades_list)

    return {
        "submission_id": submission_id,
        "status": "graded",
        "total_earned": round(total_earned, 1),
        "total_possible": round(total_possible, 1),
        "percentage": round(total_earned / max(total_possible, 1) * 100, 1),
        "grades": grades_list,
    }


def grade_manual_submission(
    assignment_id: str,
    scores: dict,
    student_id: str | None = None,
    student_name: str | None = None,
) -> dict:
    """Teacher enters scores directly."""
    log.info(f"[Grading] Processing manual entry for assignment {assignment_id}")

    assignment = _get_assignment(assignment_id)
    if not assignment:
        return {"error": "Assignment not found"}

    questions = assignment.get("questions", [])
    grades_list = []
    for qnum_str, pts in scores.items():
        qnum = int(qnum_str)
        correct_answer = ""
        possible = 1.0
        for q in questions:
            if q.get("question_number") == qnum:
                correct_answer = q.get("answer", "")
                break

        grades_list.append({
            "question_number": qnum,
            "student_response": f"({pts} pts)",
            "correct_answer": correct_answer,
            "points_earned": float(pts),
            "points_possible": possible,
            "feedback": "Manually entered by teacher",
            "needs_review": False,
        })

    submission_id = _store_submission(
        assignment_id, student_id, student_name, "manual",
        None, scores, None, None, "graded",
    )
    _store_grades(submission_id, grades_list)
    _update_mastery(student_id, grades_list, questions)

    total_earned = sum(g["points_earned"] for g in grades_list)
    total_possible = sum(g["points_possible"] for g in grades_list)

    return {
        "submission_id": submission_id,
        "status": "graded",
        "total_earned": round(total_earned, 1),
        "total_possible": round(total_possible, 1),
        "percentage": round(total_earned / max(total_possible, 1) * 100, 1),
        "grades": grades_list,
    }


def _grade_responses(
    responses: dict,
    questions: list[dict],
    ak_items: list[dict],
    confidence: dict | None = None,
) -> list[dict]:
    """Grade a set of responses against questions and answer key."""
    grades = []

    for q in questions:
        qnum = q.get("question_number", 0)
        correct = q.get("answer", "")

        # Override correct answer from rubric if available
        for ak in ak_items:
            if ak.get("question_number") == qnum:
                correct = ak.get("correct_answer", correct)
                break

        student_resp = responses.get(str(qnum), responses.get(qnum, ""))
        conf = float((confidence or {}).get(str(qnum), 1.0))
        needs_review = conf < 0.5

        if not student_resp:
            grades.append({
                "question_number": qnum,
                "student_response": "",
                "correct_answer": correct,
                "points_earned": 0.0,
                "points_possible": 1.0,
                "feedback": "No response detected",
                "needs_review": needs_review,
            })
            continue

        result = grade_question(student_resp, correct)
        grades.append({
            "question_number": qnum,
            "student_response": student_resp,
            "correct_answer": correct,
            "points_earned": result["points_earned"],
            "points_possible": result["points_possible"],
            "feedback": result["feedback"],
            "needs_review": needs_review or result.get("needs_review", False),
        })

    return grades
