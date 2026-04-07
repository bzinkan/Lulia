"""
Voice Cloning — ElevenLabs Instant Voice Cloning (premium feature).

Teachers can upload a 1-3 minute audio sample to clone their own voice
for video narration.
"""
import logging
import os
from uuid import uuid4

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


def clone_voice_from_sample(teacher_id: str, audio_file_path: str, voice_name: str) -> dict:
    """
    Clone a teacher's voice from an audio sample.
    Returns {voice_id, name} or {error}.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return {"error": "ELEVENLABS_API_KEY not configured"}

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=api_key)
        with open(audio_file_path, "rb") as f:
            voice = client.clone(
                name=voice_name,
                files=[f],
                description=f"Lulia voice clone for teacher {teacher_id[:8]}",
            )

        voice_id = voice.voice_id

        # Store in teachers table
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE teachers SET custom_voice_id = %s WHERE teacher_id = %s",
            (voice_id, teacher_id),
        )
        conn.commit()
        cur.close()
        conn.close()

        log.info(f"[Voice Clone] Created voice {voice_id} for teacher {teacher_id[:8]}")
        return {"voice_id": voice_id, "name": voice_name}

    except Exception as e:
        log.error(f"[Voice Clone] Failed: {e}")
        return {"error": str(e)}


def delete_cloned_voice(teacher_id: str) -> bool:
    """Remove a teacher's cloned voice."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT custom_voice_id FROM teachers WHERE teacher_id = %s", (teacher_id,))
    row = cur.fetchone()
    voice_id = row[0] if row else None

    if voice_id:
        try:
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if api_key:
                from elevenlabs import ElevenLabs
                client = ElevenLabs(api_key=api_key)
                client.voices.delete(voice_id)
        except Exception as e:
            log.warning(f"Failed to delete voice from ElevenLabs: {e}")

    cur.execute("UPDATE teachers SET custom_voice_id = NULL WHERE teacher_id = %s", (teacher_id,))
    conn.commit()
    cur.close()
    conn.close()
    return True


def get_teacher_voice(teacher_id: str) -> str | None:
    """Get teacher's custom voice ID if they have one."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT custom_voice_id FROM teachers WHERE teacher_id = %s", (teacher_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row and row[0] else None
