"""Plan routes — suggest, approve, modify, start-over, list."""
import logging
import os
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.crews.planning_crew import run_planner, approve_plan
from src.lms_agents.tools.auth import require_teacher, assert_owner_or_403

log = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_db_conn():
    """Direct (non-generator) pooled connection — used from background threads
    and other call sites that can't `yield`. Caller still invokes `.close()`,
    which releases back to the pool.
    """
    return _pool_get_connection()


class SuggestPlanRequest(BaseModel):
    class_id: str = "00000000-0000-0000-0000-000000000010"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    duration_type: str = "week"
    selected_days: list[str] | None = None
    week_start_date: str | None = None
    design_theme: str = "modern_clean"
    # Teacher preferences for what to generate
    material_types: list[str] | None = None       # ['worksheet', 'interactive', 'quiz_test', 'slides', 'video', 'forms']
    content_source: str | None = None              # 'curriculum' | 'standards' | 'custom'
    custom_prompt: str | None = None               # teacher's description of what to teach
    standards_input: str | None = None             # comma-separated standard codes


class ModifyPlanRequest(BaseModel):
    daily_plans: list[dict] | None = None


@router.post("/suggest")
async def suggest_plan(
    req: SuggestPlanRequest,
    teacher_id: str = Depends(require_teacher),
):
    """
    Trigger the Lesson Planner to generate a plan.
    Returns the plan for preview before approval.
    """
    week_start = None
    if req.week_start_date:
        try:
            week_start = date.fromisoformat(req.week_start_date)
        except ValueError:
            return JSONResponse({"error": "Invalid date format"}, status_code=400)

    req.teacher_id = teacher_id
    conn_check = get_db_conn()
    cur_check = conn_check.cursor()
    cur_check.execute(
        "SELECT teacher_id FROM classes WHERE class_id = %s::uuid",
        (req.class_id,),
    )
    cls = cur_check.fetchone()
    cur_check.close()
    conn_check.close()
    if not cls:
        return JSONResponse({"error": "Class not found"}, status_code=404)
    assert_owner_or_403(teacher_id, cls[0])

    result = run_planner(
        class_id=req.class_id,
        teacher_id=req.teacher_id,
        duration_type=req.duration_type,
        selected_days=req.selected_days,
        week_start_date=week_start,
        design_theme=req.design_theme,
        material_types=req.material_types,
        content_source=req.content_source,
        custom_prompt=req.custom_prompt,
        standards_input=req.standards_input,
    )
    return result


class ApproveRequest(BaseModel):
    sync_to_classroom: bool = False


@router.put("/{plan_id}/approve")
async def approve(
    plan_id: UUID,
    req: ApproveRequest = ApproveRequest(),
    teacher_id: str = Depends(require_teacher),
):
    """
    Approve the plan — kicks off material generation in the background.

    Returns immediately with status='generating'. The frontend polls
    GET /plans/{id} to check progress. The plan_data.generation_progress
    field updates after each material finishes:
      { completed: 2, total: 5, assignments: [...] }

    When all materials are done, plan status changes to 'complete'.
    """
    import inngest as _inngest
    from src.lms_agents.inngest.client import inngest_client

    plan_id_str = str(plan_id)
    conn_check = get_db_conn()
    cur_check = conn_check.cursor(cursor_factory=RealDictCursor)
    cur_check.execute("SELECT teacher_id FROM lesson_plans WHERE plan_id = %s", (plan_id_str,))
    row = cur_check.fetchone()
    cur_check.close()
    conn_check.close()
    if not row:
        return JSONResponse({"error": "Plan not found"}, status_code=404)
    assert_owner_or_403(teacher_id, row["teacher_id"])

    # Update status to generating immediately
    conn_pre = get_db_conn()
    cur_pre = conn_pre.cursor()
    cur_pre.execute(
        "UPDATE lesson_plans SET status = 'generating', approved_at = NOW() WHERE plan_id = %s",
        (plan_id_str,),
    )
    conn_pre.commit()
    cur_pre.close()
    conn_pre.close()

    # Fire Inngest event — the plan_approval function picks it up with
    # automatic retries and observability via the Inngest dashboard.
    await inngest_client.send(
        _inngest.Event(
            name="plan/approval.requested",
            data={
                "plan_id": plan_id_str,
                "sync_to_classroom": req.sync_to_classroom,
            },
        )
    )

    return {"plan_id": plan_id_str, "status": "generating"}


@router.put("/{plan_id}/modify")
async def modify_plan(
    plan_id: UUID,
    req: ModifyPlanRequest,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Update specific days/work_orders in a plan."""
    cur = conn.cursor()
    if req.daily_plans:
        cur.execute(
            """UPDATE lesson_plans
               SET plan_data = jsonb_set(plan_data, '{daily_plans}', %s),
                   status = 'suggested'
               WHERE plan_id = %s AND teacher_id = %s::uuid""",
            (Json(req.daily_plans), str(plan_id), teacher_id),
        )
        if cur.rowcount == 0:
            cur.close()
            return JSONResponse({"error": "Plan not found"}, status_code=404)
    conn.commit()
    cur.close()
    return {"plan_id": str(plan_id), "status": "modified"}


@router.put("/{plan_id}/start-over")
async def start_over(
    plan_id: UUID,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Discard plan and re-suggest."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE lesson_plans SET status = 'discarded' WHERE plan_id = %s AND teacher_id = %s::uuid",
        (str(plan_id), teacher_id),
    )
    if cur.rowcount == 0:
        cur.close()
        return JSONResponse({"error": "Plan not found"}, status_code=404)
    conn.commit()
    cur.close()
    return {"plan_id": str(plan_id), "status": "discarded"}


@router.get("/{plan_id}")
async def get_plan(
    plan_id: UUID,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Get plan details with status."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT plan_id, class_id, teacher_id, duration_type, selected_days,
                  week_start_date, status, plan_data, approved_at, created_at
           FROM lesson_plans WHERE plan_id = %s""",
        (str(plan_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Plan not found"}, status_code=404)
    assert_owner_or_403(teacher_id, row["teacher_id"])
    return dict(row)


@router.get("")
async def list_plans(
    class_id: Optional[str] = Query(None),
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """List plans for a class."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if class_id:
        cur.execute(
            """SELECT plan_id, class_id, duration_type, week_start_date, status, created_at
               FROM lesson_plans WHERE class_id = %s::uuid AND teacher_id = %s::uuid
               ORDER BY created_at DESC LIMIT 20""",
            (class_id, teacher_id),
        )
    else:
        cur.execute(
            """SELECT plan_id, class_id, duration_type, week_start_date, status, created_at
               FROM lesson_plans WHERE teacher_id = %s::uuid ORDER BY created_at DESC LIMIT 20""",
            (teacher_id,),
        )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"plans": rows}
