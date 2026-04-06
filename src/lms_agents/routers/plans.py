"""Plan routes — suggest, approve, modify, start-over, list."""
import os
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.crews.planning_crew import run_planner, approve_plan

router = APIRouter(prefix="/plans", tags=["Plans"])


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


class SuggestPlanRequest(BaseModel):
    class_id: str = "00000000-0000-0000-0000-000000000010"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    duration_type: str = "week"
    selected_days: list[str] | None = None
    week_start_date: str | None = None
    design_theme: str = "modern_clean"


class ModifyPlanRequest(BaseModel):
    daily_plans: list[dict] | None = None


@router.post("/suggest")
async def suggest_plan(req: SuggestPlanRequest):
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

    result = run_planner(
        class_id=req.class_id,
        teacher_id=req.teacher_id,
        duration_type=req.duration_type,
        selected_days=req.selected_days,
        week_start_date=week_start,
        design_theme=req.design_theme,
    )
    return result


@router.put("/{plan_id}/approve")
async def approve(plan_id: UUID):
    """Approve the plan — triggers generation of all work_orders."""
    result = approve_plan(str(plan_id))
    return result


@router.put("/{plan_id}/modify")
async def modify_plan(plan_id: UUID, req: ModifyPlanRequest, conn=Depends(get_db)):
    """Update specific days/work_orders in a plan."""
    cur = conn.cursor()
    if req.daily_plans:
        cur.execute(
            """UPDATE lesson_plans
               SET plan_data = jsonb_set(plan_data, '{daily_plans}', %s),
                   status = 'suggested'
               WHERE plan_id = %s""",
            (Json(req.daily_plans), str(plan_id)),
        )
    conn.commit()
    cur.close()
    return {"plan_id": str(plan_id), "status": "modified"}


@router.put("/{plan_id}/start-over")
async def start_over(plan_id: UUID, conn=Depends(get_db)):
    """Discard plan and re-suggest."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE lesson_plans SET status = 'discarded' WHERE plan_id = %s",
        (str(plan_id),),
    )
    conn.commit()
    cur.close()
    return {"plan_id": str(plan_id), "status": "discarded"}


@router.get("/{plan_id}")
async def get_plan(plan_id: UUID, conn=Depends(get_db)):
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
    return dict(row)


@router.get("")
async def list_plans(
    class_id: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """List plans for a class."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if class_id:
        cur.execute(
            """SELECT plan_id, class_id, duration_type, week_start_date, status, created_at
               FROM lesson_plans WHERE class_id = %s::uuid
               ORDER BY created_at DESC LIMIT 20""",
            (class_id,),
        )
    else:
        cur.execute(
            """SELECT plan_id, class_id, duration_type, week_start_date, status, created_at
               FROM lesson_plans ORDER BY created_at DESC LIMIT 20""",
        )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"plans": rows}
