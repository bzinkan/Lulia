"""Grading routes — submissions, grades, review."""
import os
from typing import Optional
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.crews.grading_crew import (
    grade_scan_submission, grade_digital_submission, grade_manual_submission,
)

router = APIRouter(prefix="", tags=["Grading"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.post("/submissions/upload")
async def upload_submission(
    assignment_id: str = Form(...),
    file: UploadFile = File(...),
    student_id: Optional[str] = Form(None),
    student_name: Optional[str] = Form(None),
):
    """Upload a scanned image/PDF for grading."""
    content = await file.read()

    # Save to MinIO
    file_url = None
    try:
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        key = f"scans/{uuid4()}/{file.filename}"
        s3.put_object(Bucket=os.environ.get("S3_BUCKET_SCANS", "lulia-scans"), Key=key, Body=content)
        file_url = key
    except ClientError:
        pass  # Non-critical — file just won't be stored

    result = grade_scan_submission(
        assignment_id=assignment_id,
        image_bytes=content,
        student_id=student_id,
        student_name=student_name,
        file_url=file_url,
    )
    return result


class DigitalSubmission(BaseModel):
    assignment_id: str
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    responses: dict  # {1: "answer", 2: "answer"}


@router.post("/submissions/digital")
async def digital_submission(req: DigitalSubmission):
    """Grade digital quiz responses."""
    result = grade_digital_submission(
        assignment_id=req.assignment_id,
        responses=req.responses,
        student_id=req.student_id,
        student_name=req.student_name,
    )
    return result


class ManualSubmission(BaseModel):
    assignment_id: str
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    scores: dict  # {1: 5, 2: 3}


@router.post("/submissions/manual")
async def manual_submission(req: ManualSubmission):
    """Teacher enters scores directly."""
    result = grade_manual_submission(
        assignment_id=req.assignment_id,
        scores=req.scores,
        student_id=req.student_id,
        student_name=req.student_name,
    )
    return result


@router.get("/submissions/{submission_id}")
async def get_submission(submission_id: UUID, conn=Depends(get_db)):
    """Get submission with grades."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM submissions WHERE submission_id = %s", (str(submission_id),))
    sub = cur.fetchone()
    if not sub:
        cur.close()
        return JSONResponse({"error": "Submission not found"}, status_code=404)

    cur.execute(
        "SELECT * FROM grades WHERE submission_id = %s ORDER BY question_number",
        (str(submission_id),),
    )
    grades = [dict(r) for r in cur.fetchall()]
    cur.close()

    result = dict(sub)
    result["grades"] = grades
    return result


@router.get("/submissions")
async def list_submissions(
    assignment_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """List submissions, optionally filtered by assignment."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    conditions = []
    params = []
    if assignment_id:
        conditions.append("assignment_id = %s::uuid")
        params.append(assignment_id)
    if status:
        conditions.append("status = %s")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(50)
    cur.execute(
        f"SELECT * FROM submissions {where} ORDER BY created_at DESC LIMIT %s",
        params,
    )
    subs = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"submissions": subs}


@router.get("/submissions/needs-review")
async def needs_review(conn=Depends(get_db)):
    """List submissions awaiting teacher review."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT s.*, a.title as assignment_title
           FROM submissions s
           JOIN assignments a ON s.assignment_id = a.assignment_id
           WHERE s.status = 'needs_review'
           ORDER BY s.created_at DESC""",
    )
    subs = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"submissions": subs}


@router.put("/grades/{grade_id}")
async def override_grade(
    grade_id: UUID,
    points_earned: float = Query(...),
    feedback: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """Teacher overrides a grade."""
    cur = conn.cursor()
    updates = ["points_earned = %s", "teacher_override = true"]
    params = [points_earned]
    if feedback:
        updates.append("feedback = %s")
        params.append(feedback)
    params.append(str(grade_id))
    cur.execute(
        f"UPDATE grades SET {', '.join(updates)} WHERE grade_id = %s",
        params,
    )
    conn.commit()
    cur.close()
    return {"grade_id": str(grade_id), "status": "overridden"}
