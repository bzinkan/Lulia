"""
Image Captioner — Gemini 2.5 Pro vision describes a teacher's uploaded
image so it can be looked up later during interactive activity generation.

Writes `description` (1-2 sentence summary) and `tags` (array of short
keywords) into the teacher_images row. Safe to call async after upload —
failure is non-fatal; the image is still available, just not searchable.
"""
import json
import logging
import os
import re
from typing import Optional

log = logging.getLogger(__name__)


def _gemini_client():
    from google import genai
    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def _fetch_image_bytes(storage_url: str) -> Optional[bytes]:
    """Download image bytes. Handles MinIO internal (`http://minio:9000/...`)
    and public (`http://localhost:9000/...`) URLs — the caption step runs
    server-side so we rewrite localhost → minio when needed."""
    import httpx
    url = storage_url
    pub = os.environ.get("S3_PUBLIC_ENDPOINT", "http://localhost:9000")
    internal = os.environ.get("S3_ENDPOINT", "http://minio:9000")
    if url.startswith(pub):
        url = internal + url[len(pub):]
    try:
        with httpx.Client(timeout=20.0) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.content
    except Exception as e:
        log.warning(f"[ImageCaptioner] Fetch failed for {url}: {e}")
        return None


def _detect_media_type(b: bytes) -> str:
    if b.startswith(b"\x89PNG"):
        return "image/png"
    if b.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if b.startswith(b"GIF8"):
        return "image/gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def caption_image(image_bytes: bytes) -> dict:
    """Return {description: str, tags: list[str]} from Gemini vision.
    Empty dict on failure."""
    try:
        from google.genai import types
        client = _gemini_client()
    except Exception as e:
        log.warning(f"[ImageCaptioner] Gemini unavailable: {e}")
        return {}

    media_type = _detect_media_type(image_bytes)
    prompt = (
        "Describe this image for a K-12 educational search index. Return ONLY "
        "JSON in this exact shape:\n\n"
        '{"description": "<1-2 sentence factual summary of what the image '
        'shows, focusing on subjects useful for classroom lessons>", '
        '"tags": ["<keyword>", "<keyword>", ...]}\n\n'
        "Tags rules: 5-12 lowercase single-word or hyphenated terms that a "
        "teacher would search for to find this image. Include subject area "
        "(e.g. 'biology', 'geometry'), specific concepts (e.g. 'plant-cell', "
        "'right-triangle'), and any prominent named entities ('amazon-river', "
        "'mount-everest'). No generic filler like 'image', 'picture', 'color'. "
        "Respond with the JSON object only — no markdown, no preamble."
    )

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                prompt,
            ],
        )
        text = (resp.text or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            log.warning(f"[ImageCaptioner] No JSON in response: {text[:200]}")
            return {}
        data = json.loads(match.group())
        desc = str(data.get("description", "")).strip()
        raw_tags = data.get("tags", []) or []
        tags = []
        seen = set()
        for t in raw_tags:
            if not isinstance(t, str):
                continue
            tag = t.strip().lower()
            tag = re.sub(r"[^\w\-]+", "-", tag).strip("-")
            if tag and tag not in seen and len(tag) <= 40:
                seen.add(tag)
                tags.append(tag)
        return {"description": desc, "tags": tags[:15]}
    except Exception as e:
        log.error(f"[ImageCaptioner] Vision call failed: {e}")
        return {}


def caption_teacher_image(image_id: str) -> bool:
    """Fetch the image row, download bytes, caption via Gemini, persist.
    Returns True on success, False on any failure (non-fatal to caller)."""
    from psycopg2.extras import RealDictCursor
    from src.lms_agents.tools.db import get_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT image_id, storage_url FROM teacher_images WHERE image_id = %s",
        (image_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        log.warning(f"[ImageCaptioner] No row for image_id={image_id}")
        return False

    image_bytes = _fetch_image_bytes(row["storage_url"])
    if not image_bytes:
        cur.close(); conn.close()
        return False

    result = caption_image(image_bytes)
    if not result:
        cur.close(); conn.close()
        return False

    cur.execute(
        """UPDATE teacher_images
           SET description = %s,
               tags = %s,
               caption_generated_at = NOW()
           WHERE image_id = %s""",
        (result.get("description", ""), result.get("tags", []), image_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    log.info(
        f"[ImageCaptioner] Captioned {image_id}: "
        f"{result.get('description', '')[:60]}... tags={result.get('tags', [])}"
    )
    return True


def backfill_captions(limit: int = 100) -> dict:
    """Caption every teacher_images row where description IS NULL.
    Intended as a one-off script; safe to run repeatedly."""
    from psycopg2.extras import RealDictCursor
    from src.lms_agents.tools.db import get_connection

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT image_id FROM teacher_images
           WHERE description IS NULL
           ORDER BY created_at DESC
           LIMIT %s""",
        (limit,),
    )
    ids = [r["image_id"] for r in cur.fetchall()]
    cur.close(); conn.close()

    success = 0
    for img_id in ids:
        if caption_teacher_image(str(img_id)):
            success += 1
    return {"processed": len(ids), "success": success}
