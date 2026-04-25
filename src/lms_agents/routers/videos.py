"""Video routes — generate, list, retrieve, delete + Video Library endpoints."""
import os
import tempfile
from typing import Optional
from uuid import UUID, uuid4

import boto3
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.crews.video_crew import generate_video
from src.lms_agents.tools.tts_generator import list_voices
from src.lms_agents.tools.voice_cloning import clone_voice_from_sample, delete_cloned_voice, get_teacher_voice

router = APIRouter(prefix="/videos", tags=["Videos"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


class GenerateVideoRequest(BaseModel):
    assignment_id: str
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    voice_id: Optional[str] = None
    use_my_voice: bool = False
    target_duration: int = 240
    theme: str = "modern_clean"


@router.post("/generate")
async def create_video(req: GenerateVideoRequest):
    """Generate a video from an assignment. Routes to Polly (default) or ElevenLabs (premium)."""
    from src.lms_agents.tools.tts_generator import get_provider_for_voice
    from src.lms_agents.tools.voice_cloning import get_teacher_voice
    from src.lms_agents.tools.db import get_connection as get_conn
    from psycopg2.extras import RealDictCursor as RDC

    # Check teacher tier
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RDC)
    cur.execute("SELECT COALESCE((SELECT tier FROM credit_accounts WHERE teacher_id = %s::uuid), 'basic') as tier", (req.teacher_id,))
    tier = cur.fetchone()["tier"]
    cur.close()
    conn.close()

    # Check if voice requires premium
    voice = req.voice_id or "Joanna"
    custom_voice = get_teacher_voice(req.teacher_id)
    provider = get_provider_for_voice(voice, custom_voice, tier)

    if provider == "elevenlabs" and tier not in ("premium", "max"):
        return JSONResponse(
            {"error": "Premium voice requires a premium subscription. Upgrade to use ElevenLabs voices and voice cloning.",
             "upgrade_required": True},
            status_code=402,
        )

    # Fire Inngest event — video generation runs as a retryable background step.
    # generate_video() handles the full pipeline + DB persistence internally.
    import inngest as _inngest
    from src.lms_agents.inngest.client import inngest_client

    await inngest_client.send(
        _inngest.Event(
            name="video/generation.requested",
            data={
                "assignment_id": req.assignment_id,
                "teacher_id": req.teacher_id,
                "voice_id": req.voice_id,
                "use_my_voice": req.use_my_voice,
                "target_duration": req.target_duration,
                "theme": req.theme,
            },
        )
    )

    return {"status": "generating", "message": "Video generation started"}


@router.get("/voices")
async def available_voices(teacher_id: str = Query("00000000-0000-0000-0000-000000000001")):
    """List available voices grouped by tier (standard=Polly, premium=ElevenLabs)."""
    custom = get_teacher_voice(teacher_id)
    voices = list_voices(teacher_id=teacher_id, custom_voice_id=custom)
    return {"voices": voices, "default_voice": "Joanna"}


# ---------------------------------------------------------------------------
# IMPORTANT: the /library, /upload/presign, /upload/complete routes must be
# declared BEFORE /{video_id} so FastAPI matches the literal paths first.
# Otherwise "/library" is interpreted as a video_id UUID and fails validation.
# ---------------------------------------------------------------------------

def _get_s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )


_LIBRARY_BUCKET = "lulia-generated"


@router.get("/library")
async def browse_library(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    class_id: Optional[str] = Query(None),
    grade_band: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    source_lane: Optional[str] = Query(None),
    standard_code: Optional[str] = Query(None),
    duration_max: Optional[int] = Query(None),
    video_kind: Optional[str] = Query(None, regex=r"^(short_clip|explainer_video)$"),
    limit: int = Query(48, le=200),
    offset: int = Query(0),
    conn=Depends(get_db),
):
    """Browse the class-scoped video library.

    Visibility rule:
      - scope='public'  → everyone
      - scope='teacher' → only the uploading teacher
      - scope='class'   → teachers of that class_id
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
        SELECT DISTINCT v.video_id, v.title, v.duration_seconds, v.thumbnail_url,
                        v.file_url, v.hosting_type, v.youtube_video_id, v.external_url,
                        v.grade_level, v.subject, v.domain, v.grade_bands,
                        v.reading_level, v.source_lane, v.scope, v.attribution,
                        v.license, v.video_kind, v.created_at
        FROM videos v
    """
    wheres = [
        "(v.scope = 'public' OR (v.scope = 'teacher' AND v.teacher_id = %s::uuid)"
        " OR (v.scope = 'class' AND v.class_id = %s::uuid))"
    ]
    params: list = [teacher_id, class_id or teacher_id]
    wheres.append("COALESCE(v.status, 'ready') IN ('ready', 'complete')")

    if grade_band:
        wheres.append("%s = ANY(v.grade_bands)")
        params.append(grade_band)
    if subject:
        wheres.append("v.subject = %s")
        params.append(subject)
    if domain:
        wheres.append("v.domain ILIKE %s")
        params.append(f"%{domain}%")
    if source_lane:
        wheres.append("v.source_lane = %s")
        params.append(source_lane)
    if duration_max:
        wheres.append("(v.duration_seconds IS NULL OR v.duration_seconds <= %s)")
        params.append(duration_max)
    if video_kind:
        wheres.append("v.video_kind = %s")
        params.append(video_kind)

    if standard_code:
        sql += """
            JOIN video_standards vs ON vs.video_id = v.video_id
            JOIN standards s ON s.standard_id = vs.standard_id
        """
        wheres.append("s.code = %s")
        params.append(standard_code)

    sql += " WHERE " + " AND ".join(wheres)
    sql += " ORDER BY v.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()

    return {"videos": [dict(r) for r in rows], "limit": limit, "offset": offset}


class PresignUploadRequest(BaseModel):
    filename: str
    content_type: str = "video/mp4"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    class_id: Optional[str] = None
    title: Optional[str] = None
    video_kind: Optional[str] = None         # 'short_clip' | 'explainer_video'
    source_lane: Optional[str] = None        # 'teacher_upload' (default) | 'lulia_signature' (admin)
    scope: Optional[str] = None              # 'teacher' (default) | 'class' | 'public'


@router.post("/upload/presign")
async def upload_presign(req: PresignUploadRequest, conn=Depends(get_db)):
    """Create a videos row in 'uploading' state and return a presigned PUT URL."""
    allowed_types = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}
    if req.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"content_type must be one of {allowed_types}")

    # Validate video_kind if provided
    if req.video_kind and req.video_kind not in ("short_clip", "explainer_video"):
        raise HTTPException(status_code=400, detail="video_kind must be 'short_clip' or 'explainer_video'")

    # Validate scope/source_lane
    scope = req.scope or "teacher"
    if scope not in ("teacher", "class", "public"):
        raise HTTPException(status_code=400, detail="scope must be 'teacher', 'class', or 'public'")
    source_lane = req.source_lane or "teacher_upload"
    if source_lane not in ("teacher_upload", "lulia_signature", "oer_public_domain", "generated"):
        raise HTTPException(status_code=400, detail="invalid source_lane")

    video_id = str(uuid4())
    s3_key = f"library/uploads/{video_id}.mp4"
    s3 = _get_s3()
    try:
        presigned_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": _LIBRARY_BUCKET, "Key": s3_key, "ContentType": req.content_type},
            ExpiresIn=3600,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to presign: {e}")

    cur = conn.cursor()
    cur.execute(
        """INSERT INTO videos
            (video_id, teacher_id, class_id, title, file_url,
             status, hosting_type, source_lane, scope, video_kind)
           VALUES (%s::uuid, %s::uuid, %s, %s, %s,
                   'uploading', 'self_hosted', %s, %s, %s)""",
        (video_id, req.teacher_id, req.class_id, req.title or req.filename, s3_key,
         source_lane, scope, req.video_kind),
    )
    conn.commit()
    cur.close()

    return {
        "video_id": video_id,
        "s3_key": s3_key,
        "upload_url": presigned_url,
        "content_type": req.content_type,
        "expires_in": 3600,
    }


class CompleteUploadRequest(BaseModel):
    video_id: str


@router.post("/upload/complete")
async def upload_complete(req: CompleteUploadRequest, conn=Depends(get_db)):
    """Mark an upload complete and fire the Inngest post-processing pipeline."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT video_id, file_url, status FROM videos WHERE video_id = %s::uuid",
        (req.video_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        raise HTTPException(status_code=404, detail="video not found")

    s3 = _get_s3()
    try:
        s3.head_object(Bucket=_LIBRARY_BUCKET, Key=row["file_url"])
    except Exception:
        cur.close()
        raise HTTPException(status_code=400, detail="S3 object not found — upload incomplete")

    cur.execute(
        "UPDATE videos SET status = 'processing' WHERE video_id = %s::uuid",
        (req.video_id,),
    )
    conn.commit()
    cur.close()

    try:
        import inngest
        from src.lms_agents.inngest.client import inngest_client
        await inngest_client.send(
            inngest.Event(
                name="video/upload.completed",
                data={"video_id": req.video_id, "s3_key": row["file_url"]},
            )
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to fire Inngest event: {e}")

    return {"video_id": req.video_id, "status": "processing"}


@router.get("/{video_id}")
async def get_video(video_id: UUID, conn=Depends(get_db)):
    """Get video metadata."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM videos WHERE video_id = %s", (str(video_id),))
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Video not found"}, status_code=404)
    return dict(row)


@router.get("")
async def list_videos(
    assignment_id: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """List videos."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    conditions = []
    params = []
    if assignment_id:
        conditions.append("assignment_id = %s::uuid")
        params.append(assignment_id)
    if teacher_id:
        conditions.append("teacher_id = %s::uuid")
        params.append(teacher_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(50)
    cur.execute(f"SELECT * FROM videos {where} ORDER BY created_at DESC LIMIT %s", params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"videos": rows}


@router.delete("/{video_id}")
async def delete_video(video_id: UUID, conn=Depends(get_db)):
    """Delete a video."""
    cur = conn.cursor()
    cur.execute("DELETE FROM videos WHERE video_id = %s", (str(video_id),))
    conn.commit()
    cur.close()
    return {"status": "deleted"}


# --- Voice Cloning ---

@router.post("/voice-clone")
async def clone_voice(
    file: UploadFile = File(...),
    voice_name: str = Form("My Teaching Voice"),
    teacher_id: str = Form("00000000-0000-0000-0000-000000000001"),
):
    """Upload audio sample to clone teacher's voice (premium feature)."""
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    result = clone_voice_from_sample(teacher_id, tmp_path, voice_name)
    os.unlink(tmp_path)

    if "error" in result:
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result


@router.delete("/voice-clone")
async def remove_cloned_voice(teacher_id: str = Query("00000000-0000-0000-0000-000000000001")):
    """Remove teacher's cloned voice."""
    delete_cloned_voice(teacher_id)
    return {"status": "deleted"}


class PatchVideoRequest(BaseModel):
    title: Optional[str] = None
    grade_level: Optional[str] = None
    subject: Optional[str] = None
    domain: Optional[str] = None
    grade_bands: Optional[list[str]] = None


@router.patch("/{video_id}")
async def patch_video(video_id: UUID, req: PatchVideoRequest, conn=Depends(get_db)):
    """Teacher-override classification. Never overwritten by Haiku reclassification."""
    updates: dict = {}
    if req.title is not None:
        updates["title"] = req.title
    if req.grade_level is not None:
        updates["grade_level"] = req.grade_level
    if req.subject is not None:
        updates["subject"] = req.subject
    if req.domain is not None:
        updates["domain"] = req.domain
    if req.grade_bands is not None:
        updates["grade_bands"] = req.grade_bands
    if not updates:
        return {"status": "no_changes"}

    set_parts = ", ".join(f"{k} = %s" for k in updates)
    params = list(updates.values()) + [str(video_id)]

    cur = conn.cursor()
    cur.execute(f"UPDATE videos SET {set_parts} WHERE video_id = %s::uuid", params)
    conn.commit()
    cur.close()
    return {"status": "updated", "fields": list(updates.keys())}


class ShareVideoRequest(BaseModel):
    scope: str  # 'teacher' | 'class' | 'public'


@router.post("/{video_id}/share")
async def share_video(video_id: UUID, req: ShareVideoRequest, conn=Depends(get_db)):
    """Change a video's visibility scope. Admin-check should be added in prod."""
    if req.scope not in {"teacher", "class", "public"}:
        raise HTTPException(status_code=400, detail="scope must be teacher|class|public")
    cur = conn.cursor()
    cur.execute(
        "UPDATE videos SET scope = %s WHERE video_id = %s::uuid",
        (req.scope, str(video_id)),
    )
    conn.commit()
    cur.close()
    return {"video_id": str(video_id), "scope": req.scope}
