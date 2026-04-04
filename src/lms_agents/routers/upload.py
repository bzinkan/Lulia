"""Upload routes — standards, curriculum, materials."""
import json
import logging
import os
import tempfile
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Form, Query, UploadFile, File
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import Json

from src.lms_agents.tools.knowledge_ingestion import ingest_file, ingest_url

log = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

# Allowed file extensions for materials
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md"}


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


@router.post("/standards")
async def upload_standards(file: UploadFile = File(...), conn=Depends(get_db)):
    """
    Upload custom standards file (Tier 1 — highest priority).

    Expected JSON format:
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
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON file"}, status_code=400)

    fw = data.get("framework", {})
    standards = data.get("standards", [])

    if not fw.get("name") or not standards:
        return JSONResponse({"error": "Missing framework name or standards array"}, status_code=400)

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

    return {
        "framework_id": framework_id,
        "name": fw["name"],
        "tier": "custom",
        "priority": 1,
        "standards_loaded": loaded,
    }


@router.post("/materials")
async def upload_materials(
    file: UploadFile = File(None),
    url: str = Form(None),
    subject: str = Form(None),
    grade_level: str = Form(None),
    unit: str = Form(None),
    teacher_id: str = Form("00000000-0000-0000-0000-000000000000"),
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
        )
        result["s3_key"] = s3_key
        return result
    except Exception as e:
        log.error(f"Ingestion failed: {e}")
        return JSONResponse({"error": f"Processing failed: {str(e)}"}, status_code=500)
    finally:
        os.unlink(tmp_path)


@router.post("/curriculum")
async def upload_curriculum(file: UploadFile = File(...)):
    """Upload curriculum -> Calendar + RAG KB (dual pipeline)."""
    return {"filename": file.filename, "status": "stub"}
