"""Video routes — generate, list, retrieve, delete."""
import os
import tempfile
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from src.lms_agents.crews.video_crew import generate_video
from src.lms_agents.tools.tts_generator import list_voices
from src.lms_agents.tools.voice_cloning import clone_voice_from_sample, delete_cloned_voice, get_teacher_voice

router = APIRouter(prefix="/videos", tags=["Videos"])


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

    result = generate_video(
        assignment_id=req.assignment_id,
        teacher_id=req.teacher_id,
        voice_id=req.voice_id,
        use_my_voice=req.use_my_voice,
        target_duration=req.target_duration,
        theme=req.theme,
    )
    return result


@router.get("/voices")
async def available_voices(teacher_id: str = Query("00000000-0000-0000-0000-000000000001")):
    """List available voices grouped by tier (standard=Polly, premium=ElevenLabs)."""
    custom = get_teacher_voice(teacher_id)
    voices = list_voices(teacher_id=teacher_id, custom_voice_id=custom)
    return {"voices": voices, "default_voice": "Joanna"}


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
