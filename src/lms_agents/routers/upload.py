"""Upload routes — standards, curriculum, materials."""
import json
import logging
import os
import re
import tempfile
from typing import Optional
from uuid import uuid4

import anthropic
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Form, Query, UploadFile, File
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import Json

from src.lms_agents.tools.knowledge_ingestion import ingest_file, ingest_url
from src.lms_agents.tools.curriculum_importer import import_curriculum

log = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

HAIKU = "claude-haiku-4-5-20251001"

# Allowed file extensions for materials
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md"}
# Standards also accepts JSON
STANDARDS_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md", "json", "csv"}


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


def get_s3_client():
    """Return a boto3 S3 client configured for MinIO (dev) or S3 (prod)."""
    endpoint = os.environ.get("S3_ENDPOINT")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", os.environ.get("AWS_ACCESS_KEY_ID")),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY")),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def _extract_text_from_file(content: bytes, filename: str, max_chars: int = 15000) -> str:
    """Extract text from PDF/DOCX/TXT for Haiku processing."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("txt", "md", "csv", "json"):
        return content.decode("utf-8", errors="ignore")[:max_chars]

    if ext == "pdf":
        try:
            import fitz
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                doc = fitz.open(tmp_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                    if len(text) > max_chars:
                        break
                doc.close()
                return text[:max_chars]
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            log.warning(f"PDF extraction failed: {e}")
            return ""

    if ext in ("docx", "doc"):
        try:
            from docx import Document
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                doc = Document(tmp_path)
                text = "\n".join(p.text for p in doc.paragraphs)
                return text[:max_chars]
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            log.warning(f"DOCX extraction failed: {e}")
            return ""

    return ""


def _haiku_extract_standards(text: str, filename: str) -> dict:
    """
    Use Claude Haiku to extract structured standards from unstructured text.

    Returns {"framework": {...}, "standards": [...]} or raises on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set — cannot extract standards from PDF/DOCX")

    client = anthropic.Anthropic(api_key=api_key)

    system = (
        "You are a standards extraction specialist. You read educational standards "
        "documents from schools, dioceses, states, and districts and extract every "
        "individual standard into a structured JSON format. Be thorough — extract "
        "EVERY standard you can find, not just a sample. Preserve the exact codes "
        "and descriptions from the document."
    )

    user = f"""Extract all educational standards from this document into structured JSON.

Document: {filename}

--- DOCUMENT TEXT ---
{text[:12000]}
--- END DOCUMENT TEXT ---

Return a JSON object with this exact structure:
{{
  "framework": {{
    "name": "<name of the standards framework, inferred from the document>",
    "authority": "<organization that published these standards>",
    "subjects": ["<list of subjects covered>"]
  }},
  "standards": [
    {{
      "code": "<the standard code exactly as written, e.g. 4.NF.1 or OH.SC.6.ES.1>",
      "description": "<the full text description of the standard>",
      "grade": "<grade level, e.g. 4, K, 9-10>",
      "subject": "<subject area, e.g. Math, ELA, Science>",
      "domain": "<domain or strand, e.g. Number and Operations, Reading Literature>"
    }}
  ]
}}

Rules:
- Extract EVERY standard, not just a few examples
- Use the exact code from the document — do not invent codes
- If the document uses numbering instead of codes (like "1.", "2."), create codes from the subject, grade, and number
- If no explicit code exists, create one from context (e.g., "CUSTOM.MATH.4.1")
- The description should be the full text of what students should know or be able to do
- Include the grade level for each standard
- Respond with ONLY the JSON object"""

    resp = client.messages.create(
        model=HAIKU,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    text_resp = resp.content[0].text

    # Extract JSON from response
    try:
        return json.loads(text_resp)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text_resp)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError("Could not parse standards from Haiku response")


@router.post("/standards")
async def upload_standards(file: UploadFile = File(...), conn=Depends(get_db)):
    """
    Upload custom standards file (Tier 1 — highest priority).

    Accepts:
      - JSON: Direct structured format (fast-track, no LLM needed)
      - PDF/DOCX/TXT: Any readable standards document — Claude Haiku
        extracts the individual standards automatically.

    JSON format (if using JSON directly):
    {
      "framework": {
        "name": "Archdiocese of Cincinnati Standards",
        "authority": "Archdiocese of Cincinnati",
        "subjects": ["Math", "ELA"]
      },
      "standards": [
        {"code": "ADC.4.NF.1", "description": "...", "grade": "4",
         "subject": "Math", "domain": "Number and Operations"}
      ]
    }
    """
    content = await file.read()
    filename = file.filename or "standards"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in STANDARDS_EXTENSIONS:
        return JSONResponse(
            {"error": f"Unsupported file type: .{ext}. Upload PDF, DOCX, TXT, or JSON."},
            status_code=400,
        )

    # ── Path 1: JSON fast-track ──
    if ext == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid JSON file"}, status_code=400)

        fw = data.get("framework", {})
        standards = data.get("standards", [])

        if not fw.get("name") or not standards:
            return JSONResponse(
                {"error": "Missing 'framework.name' or 'standards' array in JSON"},
                status_code=400,
            )
    else:
        # ── Path 2: PDF/DOCX/TXT → Haiku extraction ──
        log.info(f"[Standards] Extracting standards from {ext.upper()}: {filename}")

        text = _extract_text_from_file(content, filename)
        if not text or len(text.strip()) < 50:
            return JSONResponse(
                {"error": "Could not extract readable text from this file. The file may be scanned/image-only or corrupted."},
                status_code=400,
            )

        try:
            data = _haiku_extract_standards(text, filename)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except Exception as e:
            log.error(f"[Standards] Haiku extraction failed: {e}")
            return JSONResponse(
                {"error": f"Standards extraction failed: {str(e)}"},
                status_code=500,
            )

        fw = data.get("framework", {})
        standards = data.get("standards", [])

        if not standards:
            return JSONResponse(
                {"error": "No standards could be extracted from this document. Please check that it contains educational standards with codes and descriptions."},
                status_code=400,
            )

        # Auto-fill framework name if Haiku didn't provide one
        if not fw.get("name"):
            fw["name"] = filename.rsplit(".", 1)[0].replace("_", " ").title()

    # ── Store in database (same for both paths) ──
    cur = conn.cursor()
    framework_id = str(uuid4())
    cur.execute(
        """INSERT INTO standards_frameworks
           (framework_id, name, tier, state_code, authority, subjects_covered,
            grade_range, is_active, priority)
           VALUES (%s, %s, 'custom', NULL, %s, %s, NULL, true, 1)
           RETURNING framework_id""",
        (framework_id, fw["name"], fw.get("authority"), Json(fw.get("subjects", []))),
    )

    loaded = 0
    for std in standards:
        code = std.get("code", "")
        description = std.get("description", "")
        if not code or not description:
            continue
        cur.execute(
            """INSERT INTO standards
               (standard_id, framework_id, code, description, grade_level,
                subject, domain, cluster, cognitive_level)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (str(uuid4()), framework_id, code, description,
             std.get("grade"), std.get("subject"), std.get("domain"),
             std.get("cluster"), std.get("cognitive_level")),
        )
        loaded += 1

    conn.commit()
    cur.close()

    extraction_method = "json_direct" if ext == "json" else "haiku_extraction"
    return {
        "framework_id": framework_id,
        "name": fw["name"],
        "tier": "custom",
        "priority": 1,
        "standards_loaded": loaded,
        "extraction_method": extraction_method,
    }


@router.post("/materials")
async def upload_materials(
    file: UploadFile = File(None),
    url: str = Form(None),
    subject: str = Form(None),
    grade_level: str = Form(None),
    unit: str = Form(None),
    teacher_id: str = Form("00000000-0000-0000-0000-000000000000"),
    class_id: str = Form(None),
    scope: str = Form("class"),
):
    """
    Upload teaching materials to the RAG Knowledge Base.

    Accepts either a file upload (PDF, DOCX, TXT) or a URL.
    Files are saved to MinIO (lulia-uploads), then processed through
    the ingestion pipeline: chunk → embed → tag → store.
    """
    if not file and not url:
        return JSONResponse(
            {"error": "Provide either a file or a URL"},
            status_code=400,
        )

    # --- URL upload ---
    if url:
        result = ingest_url(
            url=url,
            name=url,
            teacher_id=teacher_id,
            subject=subject,
            grade_level=grade_level,
            class_id=class_id,
            scope=scope,
        )
        return result

    # --- File upload ---
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            {"error": f"Unsupported file type: .{ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"},
            status_code=400,
        )

    # Save to MinIO
    s3_key = f"materials/{uuid4()}/{filename}"
    content = await file.read()

    try:
        s3 = get_s3_client()
        bucket = os.environ.get("S3_BUCKET_UPLOADS", "lulia-uploads")
        s3.put_object(Bucket=bucket, Key=s3_key, Body=content)
        log.info(f"Saved to MinIO: {bucket}/{s3_key}")
    except ClientError as e:
        log.error(f"MinIO upload failed: {e}")
        return JSONResponse({"error": "File storage failed"}, status_code=500)

    # Write to temp file for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = ingest_file(
            file_path=tmp_path,
            file_type=ext,
            name=filename,
            teacher_id=teacher_id,
            upload_lane="materials",
            subject=subject,
            grade_level=grade_level,
            unit=unit,
            class_id=class_id,
            scope=scope,
        )
        result["s3_key"] = s3_key

        # Auto-classify the uploaded source for reference-grounded generation.
        # This makes the material immediately usable as a structural exemplar.
        source_id = result.get("source_id")
        if source_id:
            try:
                from src.lms_agents.tools.reference_analyzer import analyze_source
                meta = analyze_source(source_id, write_to_chunks=True)
                if meta:
                    result["reference_metadata"] = {
                        "artifact_type": meta.get("artifact_type"),
                        "content_shape": meta.get("content_shape_description"),
                    }
                    log.info(f"[Upload] Auto-classified as: {meta.get('artifact_type')}")
            except Exception as e:
                log.warning(f"[Upload] Auto-classify failed (non-fatal): {e}")

        return result
    except Exception as e:
        log.error(f"Ingestion failed: {e}")
        return JSONResponse({"error": f"Processing failed: {str(e)}"}, status_code=500)
    finally:
        os.unlink(tmp_path)


@router.post("/curriculum")
async def upload_curriculum(
    file: UploadFile = File(...),
    class_id: str = Form(...),
    subject: str = Form(None),
    grade_level: str = Form(None),
    teacher_id: str = Form("00000000-0000-0000-0000-000000000001"),
    week_start: str = Form(None),
):
    """
    Upload curriculum/pacing guide — dual pipeline.

    1. Full text → RAG Knowledge Base (for agent search)
    2. Parsed pacing → curriculum_calendar (for Planner scheduling)
    """
    from datetime import date as date_type

    filename = file.filename or "curriculum"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            {"error": f"Unsupported file type: .{ext}"},
            status_code=400,
        )

    # Save to MinIO
    s3_key = f"curriculum/{uuid4()}/{filename}"
    content = await file.read()

    try:
        s3 = get_s3_client()
        bucket = os.environ.get("S3_BUCKET_UPLOADS", "lulia-uploads")
        s3.put_object(Bucket=bucket, Key=s3_key, Body=content)
    except ClientError as e:
        log.error(f"MinIO upload failed: {e}")
        return JSONResponse({"error": "File storage failed"}, status_code=500)

    # Write to temp file for processing
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    start_date = None
    if week_start:
        try:
            start_date = date_type.fromisoformat(week_start)
        except ValueError:
            pass

    try:
        result = import_curriculum(
            file_path=tmp_path,
            file_type=ext,
            name=filename,
            teacher_id=teacher_id,
            class_id=class_id,
            subject=subject,
            grade_level=grade_level,
            week_start=start_date,
        )
        result["s3_key"] = s3_key
        return result
    except Exception as e:
        log.error(f"Curriculum import failed: {e}")
        return JSONResponse({"error": f"Processing failed: {str(e)}"}, status_code=500)
    finally:
        os.unlink(tmp_path)


@router.post("/school-calendar")
async def upload_school_calendar(
    file: UploadFile = File(...),
    teacher_id: str = Form("00000000-0000-0000-0000-000000000001"),
    school_year: str = Form("2025-2026"),
):
    """
    Legacy one-shot: parse AND store in one call.
    Prefer /school-calendar/parse + /school-calendar/confirm for the teacher review flow.
    """
    from src.lms_agents.tools.school_calendar import (
        parse_school_calendar_with_haiku,
        store_school_calendar,
    )

    content = await file.read()
    filename = file.filename or "school_calendar"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in {"pdf", "docx", "doc", "txt", "csv"}:
        return JSONResponse({"error": f"Unsupported file type: .{ext}"}, status_code=400)

    text = _extract_text_from_file(content, filename)
    if not text or len(text.strip()) < 30:
        return JSONResponse({"error": "Could not extract readable text from this file."}, status_code=400)

    entries = parse_school_calendar_with_haiku(text, school_year)
    if not entries:
        return JSONResponse({"error": "No calendar dates could be extracted from this document."}, status_code=400)

    stored = store_school_calendar(teacher_id, entries, school_year)
    return {
        "stored": stored,
        "total_extracted": len(entries),
        "school_year": school_year,
        "sample": entries[:5],
    }


@router.post("/school-calendar/parse")
async def parse_school_calendar(
    file: UploadFile = File(...),
    school_year: str = Form("2025-2026"),
):
    """
    Phase 1 of review-before-save: extract entries via Haiku and return to teacher.
    Does NOT write to the database.
    """
    from src.lms_agents.tools.school_calendar import parse_school_calendar_with_haiku

    content = await file.read()
    filename = file.filename or "school_calendar"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in {"pdf", "docx", "doc", "txt", "csv"}:
        return JSONResponse({"error": f"Unsupported file type: .{ext}"}, status_code=400)

    text = _extract_text_from_file(content, filename)
    if not text or len(text.strip()) < 30:
        return JSONResponse({"error": "Could not extract readable text from this file."}, status_code=400)

    entries = parse_school_calendar_with_haiku(text, school_year)
    if not entries:
        return JSONResponse({"error": "No calendar dates could be extracted from this document."}, status_code=400)

    try:
        entries.sort(key=lambda e: e.get("date", ""))
    except Exception:
        pass

    return {
        "school_year": school_year,
        "entries": entries,
        "total": len(entries),
    }


class ConfirmEntry(BaseModel):
    date: str
    day_type: str
    label: Optional[str] = None


class ConfirmCalendarRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    school_year: str = "2025-2026"
    entries: list[ConfirmEntry]


@router.post("/school-calendar/confirm")
async def confirm_school_calendar(req: ConfirmCalendarRequest):
    """Phase 2 of review-before-save: store only the teacher-approved entries."""
    from src.lms_agents.tools.school_calendar import store_school_calendar

    entries = [e.model_dump() for e in req.entries]
    stored = store_school_calendar(req.teacher_id, entries, req.school_year)
    return {
        "stored": stored,
        "total_submitted": len(entries),
        "school_year": req.school_year,
    }
