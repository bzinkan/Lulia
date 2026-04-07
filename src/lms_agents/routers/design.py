"""Design Studio routes — custom templates CRUD + AI Fill."""
import os
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.ai_fill_engine import ai_fill_template, render_custom_template

router = APIRouter(prefix="/design", tags=["Design Studio"])


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


class CreateTemplateRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    name: str
    description: str = ""
    canvas_json: dict = {}
    design_theme: str = "modern_clean"
    category: str = "custom_worksheet"


class AIFillRequest(BaseModel):
    standards: list[str] = []
    topic: str = ""
    subject: str = "Mathematics"
    grade: str = "4"
    difficulty: str = "medium"
    question_count: Optional[int] = None


@router.post("/templates")
async def create_template(req: CreateTemplateRequest, conn=Depends(get_db)):
    """Create a new custom template."""
    cur = conn.cursor()
    template_id = str(uuid4())
    cur.execute(
        """INSERT INTO custom_templates
           (template_id, teacher_id, name, description, canvas_json, design_theme, category)
           VALUES (%s, %s::uuid, %s, %s, %s, %s, %s)""",
        (template_id, req.teacher_id, req.name, req.description,
         Json(req.canvas_json), req.design_theme, req.category),
    )
    conn.commit()
    cur.close()
    return {"template_id": template_id, "status": "created"}


@router.get("/templates")
async def list_templates(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    conn=Depends(get_db),
):
    """List teacher's custom templates."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT template_id, name, description, design_theme, category,
                  usage_count, is_public, created_at, updated_at
           FROM custom_templates WHERE teacher_id = %s::uuid
           ORDER BY updated_at DESC""",
        (teacher_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"templates": rows}


@router.get("/templates/{template_id}")
async def get_template(template_id: UUID, conn=Depends(get_db)):
    """Get template canvas for editing."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM custom_templates WHERE template_id = %s", (str(template_id),))
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Template not found"}, status_code=404)
    return dict(row)


@router.put("/templates/{template_id}")
async def update_template(template_id: UUID, req: CreateTemplateRequest, conn=Depends(get_db)):
    """Update template canvas."""
    cur = conn.cursor()
    cur.execute(
        """UPDATE custom_templates
           SET name = %s, description = %s, canvas_json = %s,
               design_theme = %s, category = %s, updated_at = NOW()
           WHERE template_id = %s""",
        (req.name, req.description, Json(req.canvas_json),
         req.design_theme, req.category, str(template_id)),
    )
    conn.commit()
    cur.close()
    return {"template_id": str(template_id), "status": "updated"}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: UUID, conn=Depends(get_db)):
    """Delete a custom template."""
    cur = conn.cursor()
    cur.execute("DELETE FROM custom_templates WHERE template_id = %s", (str(template_id),))
    conn.commit()
    cur.close()
    return {"status": "deleted"}


@router.post("/templates/{template_id}/duplicate")
async def duplicate_template(template_id: UUID, conn=Depends(get_db)):
    """Copy a template."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM custom_templates WHERE template_id = %s", (str(template_id),))
    orig = cur.fetchone()
    if not orig:
        cur.close()
        return JSONResponse({"error": "Template not found"}, status_code=404)

    new_id = str(uuid4())
    cur2 = conn.cursor()
    cur2.execute(
        """INSERT INTO custom_templates
           (template_id, teacher_id, name, description, canvas_json, design_theme, category)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (new_id, str(orig["teacher_id"]), f"{orig['name']} (Copy)",
         orig["description"], Json(orig["canvas_json"]), orig["design_theme"], orig["category"]),
    )
    conn.commit()
    cur.close()
    cur2.close()
    return {"template_id": new_id, "status": "duplicated"}


@router.post("/templates/{template_id}/ai-fill")
async def fill_template(template_id: UUID, req: AIFillRequest, conn=Depends(get_db)):
    """Fill template with AI-generated content."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT canvas_json, design_theme FROM custom_templates WHERE template_id = %s", (str(template_id),))
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Template not found"}, status_code=404)

    filled = ai_fill_template(
        canvas_json=row["canvas_json"],
        standards=req.standards,
        topic=req.topic,
        subject=req.subject,
        grade=req.grade,
        difficulty=req.difficulty,
        question_count=req.question_count,
    )

    # Increment usage count
    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE custom_templates SET usage_count = usage_count + 1 WHERE template_id = %s",
        (str(template_id),),
    )
    conn.commit()
    cur2.close()

    # Render preview HTML
    html = render_custom_template(filled, row.get("design_theme", "modern_clean"))

    return {"filled_canvas": filled, "preview_html": html}


@router.post("/templates/{template_id}/preview")
async def preview_template(template_id: UUID, conn=Depends(get_db)):
    """Render template preview without saving."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT canvas_json, design_theme FROM custom_templates WHERE template_id = %s", (str(template_id),))
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Template not found"}, status_code=404)

    html = render_custom_template(row["canvas_json"], row.get("design_theme", "modern_clean"))
    return {"preview_html": html}


@router.get("/components")
async def list_components():
    """List available design components for the canvas."""
    components = [
        {"id": "header", "name": "Header Block", "category": "header", "fillable": False},
        {"id": "name_date_line", "name": "Name/Date Line", "category": "header", "fillable": False},
        {"id": "standards_badges", "name": "Standards Badges", "category": "header", "fillable": False},
        {"id": "instructions_box", "name": "Instructions", "category": "content", "fillable": True},
        {"id": "multiple_choice", "name": "Multiple Choice", "category": "question", "fillable": True},
        {"id": "fill_in_blank", "name": "Fill in the Blank", "category": "question", "fillable": True},
        {"id": "short_answer", "name": "Short Answer", "category": "question", "fillable": True},
        {"id": "long_answer", "name": "Long Answer", "category": "question", "fillable": True},
        {"id": "true_false", "name": "True/False", "category": "question", "fillable": True},
        {"id": "matching", "name": "Matching", "category": "question", "fillable": True},
        {"id": "number_problem", "name": "Number Problem", "category": "question", "fillable": True},
        {"id": "text_block", "name": "Text Block", "category": "content", "fillable": True},
        {"id": "word_bank", "name": "Word Bank", "category": "content", "fillable": True},
        {"id": "vocabulary_box", "name": "Vocabulary Box", "category": "content", "fillable": True},
        {"id": "example_box", "name": "Example Box", "category": "content", "fillable": True},
        {"id": "image_placeholder", "name": "Image Placeholder", "category": "visual", "fillable": True},
        {"id": "table", "name": "Table", "category": "visual", "fillable": True},
        {"id": "section_header", "name": "Section Header", "category": "layout", "fillable": False},
        {"id": "divider", "name": "Divider", "category": "layout", "fillable": False},
    ]
    return {"components": components}
