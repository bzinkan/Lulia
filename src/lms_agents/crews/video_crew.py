"""
Video Crew — generates educational videos from assignment content.

Pipeline: Script Agent → TTS → Slide Renderer → Video Assembler → Storage
"""
import json
import logging
import os
import re
from uuid import uuid4

import anthropic
import boto3
from psycopg2.extras import Json

from src.lms_agents.tools.db import get_connection
from src.lms_agents.tools.tts_generator import synthesize_speech, PRESET_VOICES
from src.lms_agents.tools.voice_cloning import get_teacher_voice
from src.lms_agents.tools.video_slide_renderer import render_slide
from src.lms_agents.tools.video_assembler import assemble_video, generate_thumbnail

log = logging.getLogger(__name__)
SONNET = "claude-sonnet-4-20250514"


def run_video_script_agent(
    content: dict,
    standards: list[str],
    grade: str,
    subject: str,
    target_duration: int = 240,
) -> dict:
    """
    Generate a structured video script from assignment content.
    Returns script JSON with scenes, narration, and slide content.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_script(content, standards)

    client = anthropic.Anthropic(api_key=api_key)
    questions = content.get("questions", [])
    title = content.get("title", "Lesson")

    resp = client.messages.create(
        model=SONNET,
        max_tokens=4096,
        messages=[{"role": "user", "content": (
            f"Create a video script for a grade {grade} {subject} lesson.\n\n"
            f"Title: {title}\nStandards: {', '.join(standards[:5])}\n"
            f"Content: {json.dumps(questions[:6], indent=2)}\n"
            f"Target duration: {target_duration} seconds\n\n"
            f"Generate a JSON object:\n"
            f'{{\n'
            f'  "title": "video title",\n'
            f'  "estimated_duration_seconds": {target_duration},\n'
            f'  "scenes": [\n'
            f'    {{\n'
            f'      "scene_number": 1,\n'
            f'      "duration_seconds": 15,\n'
            f'      "narration": "spoken text for TTS",\n'
            f'      "slide_content": {{"type": "title", "title": "...", "subtitle": "..."}},\n'
            f'      "visual_notes": "description"\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n\n'
            f"Include 6-10 scenes: title, concepts, examples, practice, summary.\n"
            f"Use natural speech with pauses. Grade-appropriate vocabulary.\n"
            f"Respond with ONLY the JSON."
        )}],
    )

    text = resp.content[0].text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return _fallback_script(content, standards)


def _fallback_script(content: dict, standards: list[str]) -> dict:
    """Generate a basic script without LLM."""
    title = content.get("title", "Lesson")
    questions = content.get("questions", [])

    scenes = [
        {"scene_number": 1, "duration_seconds": 10, "narration": f"Today we're learning about {title}.",
         "slide_content": {"type": "title", "title": title, "subtitle": f"Standards: {', '.join(standards[:3])}"}},
    ]
    for i, q in enumerate(questions[:5], 2):
        scenes.append({
            "scene_number": i, "duration_seconds": 20,
            "narration": f"Let's look at this problem. {q.get('question_text', '')}. The answer is {q.get('answer', '')}.",
            "slide_content": {"type": "example", "title": f"Example {i-1}", "content": q.get("question_text", "")},
        })
    scenes.append({
        "scene_number": len(scenes) + 1, "duration_seconds": 10,
        "narration": "Great job today! Keep practicing and you'll master this topic.",
        "slide_content": {"type": "title", "title": "Great Work!", "subtitle": "Keep Learning"},
    })

    return {"title": title, "estimated_duration_seconds": sum(s["duration_seconds"] for s in scenes), "scenes": scenes}


def generate_video(
    assignment_id: str,
    teacher_id: str,
    voice_id: str | None = None,
    use_my_voice: bool = False,
    target_duration: int = 240,
    theme: str = "modern_clean",
) -> dict:
    """
    Full video generation pipeline.
    Script → TTS → Slides → Assemble → Store
    """
    log.info(f"[Video] Generating for assignment {assignment_id}")

    # Get assignment content
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM assignments WHERE assignment_id = %s", (assignment_id,))
    from psycopg2.extras import RealDictCursor
    cur.close()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM assignments WHERE assignment_id = %s", (assignment_id,))
    assignment = cur.fetchone()
    cur.close()
    conn.close()

    if not assignment:
        return {"error": "Assignment not found"}

    content = {
        "title": assignment["title"],
        "questions": assignment["questions"] if isinstance(assignment["questions"], list) else [],
    }
    standards = assignment.get("standards_ids", [])

    # Resolve voice
    if use_my_voice:
        custom = get_teacher_voice(teacher_id)
        if custom:
            voice_id = custom
    if not voice_id:
        voice_id = os.environ.get("ELEVENLABS_DEFAULT_VOICE", PRESET_VOICES["rachel"]["id"])

    # 1. Generate script
    script = run_video_script_agent(content, standards, "4", "Mathematics", target_duration)
    scenes = script.get("scenes", [])

    # 2. TTS + Slides for each scene
    total_chars = 0
    assembled_scenes = []

    for scene in scenes:
        narration = scene.get("narration", "")
        total_chars += len(narration)

        # TTS
        audio_path = synthesize_speech(narration, voice_id, teacher_id) if narration else None

        # Render slide
        image_path = render_slide(scene, theme)

        assembled_scenes.append({
            "image_path": image_path,
            "audio_path": audio_path,
            "duration": scene.get("duration_seconds", 10),
        })

    # 3. Assemble video
    video_path = assemble_video(assembled_scenes)

    if not video_path:
        return {"error": "Video assembly failed", "script": script}

    # 4. Generate thumbnail
    thumb_path = generate_thumbnail(video_path)

    # 5. Upload to MinIO
    video_url = None
    thumb_url = None
    try:
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        vid_key = f"videos/{uuid4()}.mp4"
        with open(video_path, "rb") as f:
            s3.put_object(Bucket="lulia-generated", Key=vid_key, Body=f, ContentType="video/mp4")
        video_url = vid_key

        if thumb_path:
            thumb_key = f"thumbnails/{uuid4()}.jpg"
            with open(thumb_path, "rb") as f:
                s3.put_object(Bucket="lulia-generated", Key=thumb_key, Body=f, ContentType="image/jpeg")
            thumb_url = thumb_key
    except Exception as e:
        log.warning(f"Video upload failed: {e}")

    # 6. Store in DB
    video_id = str(uuid4())
    transcript = " ".join(s.get("narration", "") for s in scenes)
    duration = sum(s.get("duration", 0) for s in assembled_scenes)
    cost_estimate = total_chars * 0.00003

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO videos
               (video_id, assignment_id, teacher_id, title, duration_seconds,
                file_url, thumbnail_url, script_json, transcript_text,
                voice_used, theme_used, status, character_count, cost_estimate)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'complete', %s, %s)""",
            (video_id, assignment_id, teacher_id, script.get("title", ""), duration,
             video_url, thumb_url, Json(script), transcript,
             voice_id, theme, total_chars, cost_estimate),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to store video: {e}")
    finally:
        cur.close()
        conn.close()

    # Cleanup temp files
    for s in assembled_scenes:
        for p in [s.get("image_path"), s.get("audio_path")]:
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass
    try:
        os.unlink(video_path)
    except Exception:
        pass

    return {
        "video_id": video_id,
        "title": script.get("title", ""),
        "duration_seconds": duration,
        "scenes": len(scenes),
        "character_count": total_chars,
        "cost_estimate": round(cost_estimate, 4),
        "file_url": video_url,
        "thumbnail_url": thumb_url,
        "status": "complete",
    }
