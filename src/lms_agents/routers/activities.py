"""Interactive activity routes — generate, submit, list, analytics."""
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.interactive_generator import (
    generate_interactive_activity, submit_interactive_response,
    INTERACTIVE_TEMPLATES,
)

router = APIRouter(prefix="/interactive", tags=["Interactive"])


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


class GenerateInteractiveRequest(BaseModel):
    assignment_id: str
    interactive_template_id: str = "multiple_choice_quiz"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    class_id: Optional[str] = None
    max_attempts: int = 3
    show_answers_after: bool = True
    time_limit: Optional[int] = None


class SubmitInteractiveRequest(BaseModel):
    student_name: str
    responses: dict
    time_spent: int = 0


@router.get("/templates")
async def list_templates():
    """List available interactive activity templates."""
    templates = [
        {"id": tid, **info}
        for tid, info in INTERACTIVE_TEMPLATES.items()
    ]
    return {"templates": templates}


@router.post("/generate")
async def generate_activity(req: GenerateInteractiveRequest):
    """Generate and deploy an interactive activity."""
    result = generate_interactive_activity(
        assignment_id=req.assignment_id,
        teacher_id=req.teacher_id,
        interactive_template_id=req.interactive_template_id,
        class_id=req.class_id,
        max_attempts=req.max_attempts,
        show_answers_after=req.show_answers_after,
        time_limit=req.time_limit,
    )
    return result


@router.get("/{activity_id}/info")
async def activity_info(activity_id: UUID, conn=Depends(get_db)):
    """Public endpoint — students load activity content from here."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT activity_id, interactive_template_id, content_json,
                  max_attempts, time_limit_seconds, show_answers_after, status
           FROM interactive_activities WHERE activity_id = %s AND status = 'live'""",
        (str(activity_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Activity not found or expired"}, status_code=404)
    return dict(row)


@router.post("/{activity_id}/submit")
async def submit_response(activity_id: UUID, req: SubmitInteractiveRequest):
    """Student submits responses — no auth required."""
    result = submit_interactive_response(
        activity_id=str(activity_id),
        student_name=req.student_name,
        responses=req.responses,
        time_spent=req.time_spent,
    )
    return result


@router.get("/{activity_id}/submissions")
async def list_submissions(activity_id: UUID, conn=Depends(get_db)):
    """Teacher views all submissions for an activity."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT * FROM interactive_submissions
           WHERE activity_id = %s ORDER BY submitted_at DESC""",
        (str(activity_id),),
    )
    subs = [dict(r) for r in cur.fetchall()]
    cur.close()

    # Class average
    avg = sum(s.get("percentage", 0) for s in subs) / max(len(subs), 1) if subs else 0

    return {"submissions": subs, "count": len(subs), "class_average": round(avg, 1)}


@router.get("/{activity_id}/analytics")
async def activity_analytics(activity_id: UUID, conn=Depends(get_db)):
    """Class performance breakdown for an activity."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT AVG(percentage) as avg_score, COUNT(*) as total_submissions,
                  AVG(time_spent_seconds) as avg_time
           FROM interactive_submissions WHERE activity_id = %s""",
        (str(activity_id),),
    )
    stats = dict(cur.fetchone())
    cur.close()
    return stats


@router.get("")
async def list_activities(
    teacher_id: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """List all interactive activities."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if teacher_id:
        cur.execute(
            """SELECT ia.*, (SELECT COUNT(*) FROM interactive_submissions WHERE activity_id = ia.activity_id) as submission_count
               FROM interactive_activities ia WHERE ia.teacher_id = %s::uuid
               ORDER BY ia.created_at DESC LIMIT 50""",
            (teacher_id,),
        )
    else:
        cur.execute(
            """SELECT ia.*, (SELECT COUNT(*) FROM interactive_submissions WHERE activity_id = ia.activity_id) as submission_count
               FROM interactive_activities ia ORDER BY ia.created_at DESC LIMIT 50""",
        )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"activities": rows}


@router.delete("/{activity_id}")
async def delete_activity(activity_id: UUID, conn=Depends(get_db)):
    """Delete an interactive activity."""
    cur = conn.cursor()
    cur.execute("DELETE FROM interactive_submissions WHERE activity_id = %s", (str(activity_id),))
    cur.execute("DELETE FROM interactive_activities WHERE activity_id = %s", (str(activity_id),))
    conn.commit()
    cur.close()
    return {"status": "deleted"}
