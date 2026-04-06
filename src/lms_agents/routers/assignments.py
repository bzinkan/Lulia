"""Assignment routes — generate and retrieve."""
import os
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.crews.assignment_crew import run_assignment_crew

router = APIRouter(prefix="/assignments", tags=["Assignments"])


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


class WorkOrder(BaseModel):
    work_order_id: str = "WO-001"
    class_id: str = "00000000-0000-0000-0000-000000000010"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    output_template_id: str = "worksheet"
    output_format: str = "html"
    design_theme: str = "modern_clean"
    standards_ids: list[str] = []
    subject: str = "Mathematics"
    grade_level: str = "4"
    question_count: int = 10
    difficulty_distribution: dict = {"easy": 3, "medium": 4, "hard": 3}
    has_kb_coverage: bool = False
    accommodation_versions: list[str] = []


@router.post("/generate")
async def generate_assignment(work_order: WorkOrder):
    """
    Generate an assignment using the 5-agent crew chain.

    Curriculum Agent → Content Agent → Rubric Agent → QA Agent → Format Agent
    """
    result = run_assignment_crew(work_order.model_dump())
    return result


@router.get("/{assignment_id}")
async def get_assignment(assignment_id: UUID, conn=Depends(get_db)):
    """Get assignment detail with all content."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT assignment_id, class_id, teacher_id, work_order_id, title,
                  output_template_id, output_format, design_theme,
                  standards_ids, questions, answer_key, qa_report,
                  status, file_paths, created_at
           FROM assignments
           WHERE assignment_id = %s""",
        (str(assignment_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    return dict(row)


@router.get("/{assignment_id}/preview")
async def preview_assignment(assignment_id: UUID, version: str = "student", conn=Depends(get_db)):
    """Preview the rendered HTML for an assignment."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT questions, answer_key FROM assignments WHERE assignment_id = %s",
        (str(assignment_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    return {"assignment_id": str(assignment_id), "version": version, "status": "preview available"}
