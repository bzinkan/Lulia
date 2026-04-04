"""Upload routes — standards, curriculum, materials."""
import json
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile, File
import psycopg2
from psycopg2.extras import Json

router = APIRouter(prefix="/upload", tags=["Upload"])


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
        return {"error": "Invalid JSON file", "status": "error"}

    fw = data.get("framework", {})
    standards = data.get("standards", [])

    if not fw.get("name") or not standards:
        return {"error": "Missing framework name or standards array", "status": "error"}

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
        "status": "success",
    }


@router.post("/curriculum")
async def upload_curriculum(file: UploadFile = File(...)):
    """Upload curriculum -> Calendar + RAG KB."""
    return {"filename": file.filename, "status": "stub"}


@router.post("/materials")
async def upload_materials(file: UploadFile = File(...)):
    """Upload materials -> RAG KB."""
    return {"filename": file.filename, "status": "stub"}
