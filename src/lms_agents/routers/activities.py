"""Interactive activity routes — generate, submit, list, analytics."""
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.interactive_generator import (
    generate_interactive_activity, submit_interactive_response,
    refine_activity, REFINE_INSTRUCTIONS,
    INTERACTIVE_TEMPLATES,
)

router = APIRouter(prefix="/interactive", tags=["Interactive"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
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


@router.get("/{activity_id}/data")
async def get_activity_data(activity_id: UUID, conn=Depends(get_db)):
    """
    Return the editable data payload for a structured activity.
    Only structured templates (crossword/word_search/flashcards/timeline/
    number_line) have a `data` field — artifact-mode activities return an
    empty body with mode='artifact' so the client can route to Refine instead.
    """
    import json
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT interactive_template_id, content_json FROM interactive_activities WHERE activity_id = %s",
        (str(activity_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Activity not found"}, status_code=404)
    content = row["content_json"] or {}
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except Exception:
            content = {}
    mode = content.get("mode", "artifact")
    return {
        "activity_id": str(activity_id),
        "template_id": row["interactive_template_id"],
        "mode": mode,
        "data": content.get("data") if mode == "structured" else None,
    }


class UpdateActivityDataRequest(BaseModel):
    data: dict


@router.put("/{activity_id}/data")
async def update_activity_data(activity_id: UUID, req: UpdateActivityDataRequest,
                                conn=Depends(get_db)):
    """
    Replace the data payload for a structured activity, rebuild the HTML,
    re-upload to MinIO, and persist. Only works for templates that have a
    hand-written builder — artifact activities must use the Refine flow.
    """
    import json
    import boto3
    from psycopg2.extras import Json
    from src.lms_agents.tools.structured_common import get_builder

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT interactive_template_id, content_json, access_url FROM interactive_activities WHERE activity_id = %s",
        (str(activity_id),),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return JSONResponse({"error": "Activity not found"}, status_code=404)
    template_id = row["interactive_template_id"]
    content = row["content_json"] or {}
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except Exception:
            content = {}
    if content.get("mode") != "structured":
        cur.close()
        return JSONResponse(
            {"error": "This activity was generated in artifact mode — use the Refine endpoint instead."},
            status_code=400,
        )
    try:
        builder = get_builder(template_id)
    except ValueError as e:
        cur.close()
        return JSONResponse({"error": str(e)}, status_code=400)

    try:
        html = builder(req.data)
    except Exception as e:
        cur.close()
        return JSONResponse({"error": f"Failed to rebuild HTML: {e}"}, status_code=400)

    # Re-upload to MinIO at the same key (access_url stays stable)
    try:
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        bucket = os.environ.get("S3_BUCKET_ACTIVITIES", "lulia-activities")
        key = f"activities/{activity_id}/index.html"
        s3.put_object(Bucket=bucket, Key=key, Body=html.encode("utf-8"),
                      ContentType="text/html; charset=utf-8")
    except Exception as e:
        cur.close()
        return JSONResponse({"error": f"Upload failed: {e}"}, status_code=500)

    new_content = dict(content)
    new_content["data"] = req.data
    cur.close()
    cur = conn.cursor()
    cur.execute(
        "UPDATE interactive_activities SET content_json = %s WHERE activity_id = %s",
        (Json(new_content), str(activity_id)),
    )
    conn.commit()
    cur.close()
    return {"status": "updated", "activity_id": str(activity_id), "access_url": row["access_url"]}


# ---------------------------------------------------------------------------
# Refinement (Pattern C — post-generation chips)
# ---------------------------------------------------------------------------

class RefineRequest(BaseModel):
    instruction_id: str
    custom_instructions: Optional[str] = None


@router.get("/refinements/instructions")
async def list_refinement_instructions():
    """Return the canonical chip-id -> instruction-text map for the frontend."""
    return {"instructions": REFINE_INSTRUCTIONS}


@router.post("/{activity_id}/refine")
async def refine(activity_id: UUID, req: RefineRequest):
    """
    Apply a refinement chip to an existing activity. Creates a new activity
    row (preserves original) and returns the new activity metadata.
    """
    result = refine_activity(
        activity_id=str(activity_id),
        instruction_id=req.instruction_id,
        custom_instructions=req.custom_instructions,
    )
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result
