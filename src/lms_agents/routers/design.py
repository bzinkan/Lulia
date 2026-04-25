"""Design Studio routes — custom templates CRUD + AI Fill + Content Generation."""
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

import anthropic
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.ai_fill_engine import ai_fill_template, render_custom_template
from src.lms_agents.tools.rag_search import search_kb

log = logging.getLogger(__name__)

router = APIRouter(prefix="/design", tags=["Design Studio"])

# Load course components config once at import time
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "course_components.json"
_COURSE_COMPONENTS: dict = {}
if _CONFIG_PATH.exists():
    with open(_CONFIG_PATH, "r") as f:
        _COURSE_COMPONENTS = json.load(f)


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
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


@router.get("/course-components")
async def get_course_components():
    """Return the category → course → component mapping config."""
    return _COURSE_COMPONENTS


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


# ---------------------------------------------------------------------------
# Content Generation + Export endpoints (Design Studio v2)
# ---------------------------------------------------------------------------

SONNET = "claude-sonnet-4-20250514"


class GenerateContentRequest(BaseModel):
    topic: str
    grade: str = "4"
    subject: str = "Mathematics"
    standards: list[str] = []
    output_type: str = "worksheet"  # worksheet, infographic, poster, flashcards
    question_count: int = 10
    difficulty: str = "medium"  # easy, medium, hard
    class_id: str | None = None
    teacher_id: str = "00000000-0000-0000-0000-000000000001"


class ExportPDFRequest(BaseModel):
    content: dict  # The generated content from generate-content
    theme: str = "modern_clean"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"


class ExportGoogleRequest(BaseModel):
    content: dict
    export_type: str = "doc"  # "doc" or "slides"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"


def _suggest_standards_for_topic(
    topic: str, grade: str, subject: str, conn,
) -> tuple[list[str], list[dict]]:
    """
    Use Claude Haiku to suggest standard codes for a topic, then match in DB.
    Returns (code_list, matched_standard_rows).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return [], []

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        f"You are an expert curriculum standards specialist. "
        f"Suggest 3-6 standard codes for the following:\n"
        f"Subject: {subject}\nGrade: {grade}\nTopic: {topic}\n\n"
        f"Return a JSON object: {{\"codes\": [\"4.NF.1\", ...], "
        f"\"search_terms\": [\"equivalent fractions\", ...]}}\n"
        f"Return ONLY the JSON object."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        ai_result = json.loads(text)
    except Exception as e:
        log.warning(f"[Design] Standards suggestion failed: {e}")
        return [], []

    codes = ai_result.get("codes", [])
    search_terms = ai_result.get("search_terms", [])

    cur = conn.cursor(cursor_factory=RealDictCursor)
    matched = []

    for code in codes:
        cur.execute(
            """SELECT s.standard_id, s.code, s.description, s.grade_level, s.subject,
                      s.domain, f.name AS framework_name, f.tier, f.priority
               FROM standards s
               JOIN standards_frameworks f ON s.framework_id = f.framework_id
               WHERE f.is_active = true AND s.code ILIKE %s
               ORDER BY f.priority ASC LIMIT 3""",
            (f"%{code}%",),
        )
        matched.extend([dict(r) for r in cur.fetchall()])

    if len(matched) < 3:
        for term in search_terms:
            cur.execute(
                """SELECT s.standard_id, s.code, s.description, s.grade_level, s.subject,
                          s.domain, f.name AS framework_name, f.tier, f.priority
                   FROM standards s
                   JOIN standards_frameworks f ON s.framework_id = f.framework_id
                   WHERE f.is_active = true
                     AND s.description ILIKE %s
                     AND s.grade_level = %s
                   ORDER BY f.priority ASC LIMIT 5""",
                (f"%{term}%", grade),
            )
            matched.extend([dict(r) for r in cur.fetchall()])

    cur.close()

    # Deduplicate
    seen: set = set()
    unique = []
    for s in matched:
        sid = s["standard_id"]
        if sid not in seen:
            seen.add(sid)
            unique.append(s)

    code_list = codes if codes else [s["code"] for s in unique[:6]]
    return code_list, unique[:10]


@router.post("/generate-content")
async def generate_content(req: GenerateContentRequest, conn=Depends(get_db)):
    """
    Generate structured worksheet / activity content using RAG + Claude Sonnet.

    1. Auto-suggest standards if none provided
    2. Search RAG knowledge base for relevant chunks
    3. Call Claude Sonnet for structured content generation
    4. Return content + metadata
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(
            {"error": "ANTHROPIC_API_KEY not configured"},
            status_code=503,
        )

    # Step 1: auto-suggest standards if empty
    standards_used = list(req.standards)
    matched_standards: list[dict] = []
    if not standards_used:
        standards_used, matched_standards = _suggest_standards_for_topic(
            req.topic, req.grade, req.subject, conn,
        )

    # Step 2: RAG search for relevant content
    rag_query = f"{req.subject} Grade {req.grade}: {req.topic}"
    try:
        rag_results = search_kb(
            query=rag_query,
            teacher_id=req.teacher_id,
            class_id=req.class_id,
            subject=req.subject,
            grade=req.grade,
            standards_ids=standards_used[:5] if standards_used else None,
            top_k=5,
        )
    except Exception as e:
        log.warning(f"[Design] RAG search failed (continuing without): {e}")
        rag_results = []

    rag_chunks_text = "\n---\n".join(
        r.get("content", "")[:800] for r in rag_results
    ) or "(No reference material available)"

    rag_sources = [
        {
            "source_name": r.get("source_name", ""),
            "section_heading": r.get("section_heading", ""),
            "page_number": r.get("page_number"),
        }
        for r in rag_results
    ]

    standards_text = ", ".join(standards_used[:8]) if standards_used else "grade-appropriate"

    # Step 3: Call Claude Sonnet
    prompt = f"""You are an expert K-12 curriculum designer. Generate a {req.output_type} for Grade {req.grade} {req.subject}.

Topic: {req.topic}
Standards: {standards_text}
Difficulty: {req.difficulty}
Question count: {req.question_count}

Reference material (use this for accuracy):
{rag_chunks_text}

Generate a JSON object:
{{
  "title": "worksheet title",
  "instructions": "student instructions",
  "questions": [
    {{
      "number": 1,
      "type": "multiple_choice|short_answer|fill_in_blank|true_false|matching",
      "question_text": "the question",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "the answer",
      "points": 1,
      "standard_code": "4.NF.1",
      "difficulty": "easy|medium|hard"
    }}
  ],
  "word_bank": ["term1", "term2"],
  "vocabulary": [{{"term": "...", "definition": "..."}}],
  "answer_key": [{{"number": 1, "answer": "..."}}]
}}

Requirements:
- All content must be grade-appropriate for Grade {req.grade}
- Questions must align to the given standards
- Include a mix of question types
- Word bank should contain key terms from the topic
- Vocabulary definitions should be grade-appropriate
- Answer key must have correct answers for every question

Return ONLY the JSON object, no markdown fences."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=SONNET,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # Strip possible markdown fences
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        content = json.loads(text)
    except json.JSONDecodeError as e:
        log.error(f"[Design] Failed to parse Claude response: {e}")
        return JSONResponse(
            {"error": "AI returned invalid JSON — please retry"},
            status_code=502,
        )
    except Exception as e:
        log.error(f"[Design] Claude content generation failed: {e}")
        return JSONResponse(
            {"error": f"Content generation failed: {e}"},
            status_code=502,
        )

    return {
        "content": content,
        "standards_used": standards_used,
        "matched_standards": matched_standards,
        "rag_sources": rag_sources,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/export-pdf")
async def export_pdf(req: ExportPDFRequest):
    """
    Render generated content via Carbone PDF, with HTML fallback.

    - Primary: Carbone.io professional PDF → returns PDF binary
    - Fallback: render_custom_template() HTML if Carbone is unavailable
    """
    # Try Carbone first
    try:
        from src.lms_agents.tools.carbone_renderer import render_worksheet

        pdf_bytes = render_worksheet(req.content, req.theme)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=worksheet.pdf"},
        )
    except Exception as carbone_err:
        log.warning(f"[Design] Carbone PDF failed, falling back to HTML: {carbone_err}")

    # Fallback to HTML renderer
    try:
        canvas_for_render = _content_to_canvas(req.content)
        html = render_custom_template(canvas_for_render, req.theme)
        return {"html": html, "theme": req.theme, "note": "Carbone unavailable, HTML fallback"}
    except Exception as e:
        log.error(f"[Design] PDF export failed: {e}")
        return JSONResponse(
            {"error": f"Export failed: {e}"},
            status_code=500,
        )


@router.post("/download-pdf")
async def download_pdf(req: ExportPDFRequest):
    """
    Returns raw PDF bytes for direct browser download.

    Uses Carbone.io for professional output. Falls back to HTML
    wrapped in a JSON response if Carbone is unavailable.
    """
    try:
        from src.lms_agents.tools.carbone_renderer import render_worksheet

        pdf_bytes = render_worksheet(req.content, req.theme)
        title = req.content.get("title", "worksheet").replace(" ", "_")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{title}.pdf"'},
        )
    except Exception as e:
        log.error(f"[Design] PDF download failed: {e}")
        return JSONResponse(
            {"error": f"PDF generation failed: {e}", "message": "Please try again or use Google Docs export."},
            status_code=503,
        )


def _content_to_canvas(content: dict) -> dict:
    """
    Convert structured worksheet content into a canvas_json dict
    that render_custom_template() can consume.
    """
    components = []

    # Header
    components.append({
        "type": "header",
        "config": {"title": content.get("title", "Worksheet")},
    })
    components.append({"type": "name_date_line", "config": {}})

    # Instructions
    if content.get("instructions"):
        components.append({
            "type": "instructions_box",
            "config": {"text": content["instructions"]},
        })

    # Word bank
    if content.get("word_bank"):
        components.append({
            "type": "word_bank",
            "config": {"words": content["word_bank"]},
        })

    # Questions
    for q in content.get("questions", []):
        qtype = q.get("type", "short_answer")
        comp: dict = {"type": qtype, "config": {}}
        comp["config"]["question"] = q.get("question_text", "")
        comp["config"]["number"] = q.get("number", 0)
        comp["config"]["points"] = q.get("points", 1)

        if qtype == "multiple_choice" and q.get("options"):
            comp["config"]["options"] = q["options"]
            comp["config"]["correct"] = q.get("correct_answer", "")
        elif qtype == "true_false":
            comp["config"]["correct"] = q.get("correct_answer", "")
        elif qtype == "matching":
            comp["config"]["correct"] = q.get("correct_answer", "")
        else:
            comp["config"]["answer"] = q.get("correct_answer", "")

        components.append(comp)

    # Vocabulary
    for v in content.get("vocabulary", []):
        components.append({
            "type": "vocabulary_box",
            "config": {"term": v.get("term", ""), "definition": v.get("definition", "")},
        })

    return {"components": components}


@router.post("/export-google")
async def export_google(req: ExportGoogleRequest):
    """
    Export generated content to Google Docs or Slides.

    - doc: Creates a Google Doc with the worksheet content.
    - slides: Uses gemini_slides.create_google_slides() for a slide deck.

    Requires the teacher to have connected their Google account.
    """
    from src.lms_agents.tools.google_auth import get_credentials

    credentials = get_credentials(req.teacher_id)
    if not credentials:
        return JSONResponse(
            {
                "error": "Google account not connected",
                "message": "Please connect your Google account in Settings before exporting.",
            },
            status_code=401,
        )

    title = req.content.get("title", "Worksheet")

    try:
        if req.export_type == "slides":
            from src.lms_agents.tools.gemini_slides import (
                generate_slide_content,
                create_google_slides,
            )

            standards = [
                q.get("standard_code", "")
                for q in req.content.get("questions", [])
                if q.get("standard_code")
            ]
            slides_content = generate_slide_content(
                content=req.content,
                standards=standards,
            )
            result = create_google_slides(
                teacher_id=req.teacher_id,
                slides_content=slides_content,
                title=title,
            )
            return {
                "export_type": "slides",
                "url": result["url"],
                "presentation_id": result["presentation_id"],
            }

        else:  # doc
            from googleapiclient.discovery import build

            docs_service = build("docs", "v1", credentials=credentials)
            doc = docs_service.documents().create(body={"title": title}).execute()
            doc_id = doc["documentId"]

            # Build document content requests
            requests = _build_doc_requests(req.content)
            if requests:
                docs_service.documents().batchUpdate(
                    documentId=doc_id, body={"requests": requests},
                ).execute()

            url = f"https://docs.google.com/document/d/{doc_id}/edit"
            log.info(f"[Design] Created Google Doc: {url}")
            return {
                "export_type": "doc",
                "url": url,
                "document_id": doc_id,
            }

    except ValueError as e:
        # get_credentials or Slides may raise ValueError
        return JSONResponse(
            {"error": str(e), "message": "Please reconnect your Google account."},
            status_code=401,
        )
    except Exception as e:
        log.error(f"[Design] Google export failed: {e}")
        return JSONResponse(
            {"error": f"Google export failed: {e}"},
            status_code=500,
        )


def _build_doc_requests(content: dict) -> list[dict]:
    """
    Build Google Docs API batchUpdate requests from worksheet content.
    Inserts text at end-of-body in reverse order (Google Docs index 1 = start).
    """
    # We build text sections and insert them sequentially at index 1
    sections: list[str] = []

    # Title
    sections.append(content.get("title", "Worksheet") + "\n\n")

    # Instructions
    if content.get("instructions"):
        sections.append(f"Instructions: {content['instructions']}\n\n")

    # Word bank
    if content.get("word_bank"):
        sections.append("Word Bank: " + ", ".join(content["word_bank"]) + "\n\n")

    # Questions
    for q in content.get("questions", []):
        num = q.get("number", "")
        qtext = q.get("question_text", "")
        line = f"{num}. {qtext}\n"
        if q.get("type") == "multiple_choice" and q.get("options"):
            for i, opt in enumerate(q["options"]):
                letter = chr(65 + i)  # A, B, C, D ...
                line += f"   {letter}. {opt}\n"
        line += "\n"
        sections.append(line)

    # Vocabulary
    if content.get("vocabulary"):
        sections.append("Vocabulary\n")
        for v in content["vocabulary"]:
            sections.append(f"  {v.get('term', '')}: {v.get('definition', '')}\n")
        sections.append("\n")

    full_text = "".join(sections)
    if not full_text.strip():
        return []

    return [{"insertText": {"location": {"index": 1}, "text": full_text}}]
