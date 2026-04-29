"""Google Classroom routes — OAuth, courses, push assignments."""
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from src.lms_agents.tools.google_auth import (
    get_auth_url, handle_callback, is_connected, revoke_credentials,
)
from src.lms_agents.tools.google_classroom import (
    list_courses, list_students, create_topic, push_assignment_to_classroom,
)
from src.lms_agents.tools.google_calendar_sync import sync_plan_to_calendar
from src.lms_agents.tools.auth import require_teacher, assert_owner_or_403

router = APIRouter(prefix="/classroom", tags=["Classroom"])


# --- OAuth ---

@router.get("/auth/start")
async def start_auth(
    teacher_id: str = Depends(require_teacher),
):
    """Redirect to Google consent screen."""
    url = get_auth_url(teacher_id)
    return RedirectResponse(url)


@router.get("/auth/callback")
async def auth_callback(code: str = "", state: str = ""):
    """Handle OAuth callback from Google."""
    if not code:
        return JSONResponse({"error": "No auth code"}, status_code=400)
    result = handle_callback(code, state)
    # Redirect back to dashboard settings
    return RedirectResponse(f"http://localhost:3001/settings?google=connected")


@router.get("/status")
async def check_status(
    teacher_id: str = Depends(require_teacher),
):
    """Check if teacher is connected to Google."""
    connected = is_connected(teacher_id)
    return {"connected": connected, "teacher_id": teacher_id}


@router.post("/disconnect")
async def disconnect(
    teacher_id: str = Depends(require_teacher),
):
    """Revoke Google tokens and disconnect."""
    revoke_credentials(teacher_id)
    return {"status": "disconnected"}


# --- Courses ---

@router.get("/courses")
async def get_courses(
    teacher_id: str = Depends(require_teacher),
):
    """List teacher's active Classroom courses."""
    try:
        courses = list_courses(teacher_id)
        return {"courses": courses}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Failed to list courses: {e}"}, status_code=500)


@router.get("/courses/{course_id}/students")
async def get_students(
    course_id: str,
    teacher_id: str = Depends(require_teacher),
):
    """List students in a Classroom course."""
    try:
        students = list_students(teacher_id, course_id)
        return {"students": students}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# --- Push to Classroom ---

class PushRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    course_id: str
    topic_name: Optional[str] = None


@router.post("/push/{assignment_id}")
async def push_to_classroom(
    assignment_id: UUID,
    req: PushRequest,
    teacher_id: str = Depends(require_teacher),
):
    """Push a single assignment to Google Classroom."""
    from src.lms_agents.tools.db import get_connection
    from psycopg2.extras import RealDictCursor

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM assignments WHERE assignment_id = %s", (str(assignment_id),))
    assignment = cur.fetchone()
    cur.close()
    conn.close()

    if not assignment:
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    assert_owner_or_403(teacher_id, assignment["teacher_id"])

    # Create topic if specified
    topic_id = None
    if req.topic_name:
        try:
            topic_id = create_topic(teacher_id, req.course_id, req.topic_name)
        except Exception:
            pass  # Topic may already exist

    try:
        result = push_assignment_to_classroom(
            teacher_id=teacher_id,
            course_id=req.course_id,
            title=assignment["title"],
            description=f"Standards: {', '.join(assignment.get('standards_ids', []))}",
            topic_id=topic_id,
        )

        # Update assignment with Classroom ID
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE assignments SET google_classroom_id = %s WHERE assignment_id = %s",
            (result.get("coursework_id"), str(assignment_id)),
        )
        conn.commit()
        cur.close()
        conn.close()

        return {"status": "pushed", **result}
    except Exception as e:
        return JSONResponse({"error": f"Push failed: {e}"}, status_code=500)


# --- Calendar Sync ---

@router.post("/calendar/sync/{plan_id}")
async def sync_calendar(
    plan_id: UUID,
    calendar_id: str = Query("primary"),
    teacher_id: str = Depends(require_teacher),
):
    """Sync a plan's schedule to Google Calendar."""
    from src.lms_agents.tools.db import get_connection
    from psycopg2.extras import RealDictCursor

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT teacher_id, plan_data FROM lesson_plans WHERE plan_id = %s", (str(plan_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return JSONResponse({"error": "Plan not found"}, status_code=404)
    assert_owner_or_403(teacher_id, row["teacher_id"])

    try:
        events = sync_plan_to_calendar(teacher_id, row["plan_data"], calendar_id)
        return {"status": "synced", "events": events}
    except Exception as e:
        return JSONResponse({"error": f"Calendar sync failed: {e}"}, status_code=500)
