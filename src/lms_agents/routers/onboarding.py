"""Onboarding wizard routes."""
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/status")
async def onboarding_status(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    conn=Depends(get_db),
):
    """Check if teacher needs onboarding."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT onboarding_complete FROM teachers WHERE teacher_id = %s", (teacher_id,))
    row = cur.fetchone()
    cur.close()
    if not row:
        return {"needs_onboarding": True}
    return {"needs_onboarding": not row.get("onboarding_complete", False)}


class OnboardingStepRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    step: str  # about_you, first_class, preferences
    data: dict


@router.post("/step")
async def save_step(req: OnboardingStepRequest, conn=Depends(get_db)):
    """Save progress for an onboarding step."""
    cur = conn.cursor()
    if req.step == "about_you":
        cur.execute(
            "UPDATE teachers SET name = %s, state_code = %s, school_name = %s WHERE teacher_id = %s",
            (req.data.get("name"), req.data.get("state_code"), req.data.get("school_name"), req.teacher_id),
        )
    elif req.step == "first_class":
        class_id = str(uuid4())
        cur.execute(
            """INSERT INTO classes (class_id, teacher_id, name, subject, grade_level, school_year)
               VALUES (%s, %s::uuid, %s, %s, %s, '2026-2027')""",
            (class_id, req.teacher_id, req.data.get("name", "My Class"),
             req.data.get("subject", "Mathematics"), req.data.get("grade_level", "4")),
        )
    elif req.step == "preferences":
        cur.execute(
            "UPDATE teachers SET design_theme = %s WHERE teacher_id = %s",
            (req.data.get("theme", "modern_clean"), req.teacher_id),
        )
    conn.commit(); cur.close()
    return {"status": "saved", "step": req.step}


@router.post("/complete")
async def complete_onboarding(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    conn=Depends(get_db),
):
    """Finalize onboarding and unlock dashboard."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE teachers SET onboarding_complete = true WHERE teacher_id = %s",
        (teacher_id,),
    )
    conn.commit(); cur.close()
    return {"status": "complete"}
