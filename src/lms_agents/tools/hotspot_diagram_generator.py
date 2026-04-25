"""
Hotspot Diagram Generator — builds AI-generated labeled diagrams with
coordinate annotations for hotspot_labeling interactive activities.

Two-step pipeline (Gemini end-to-end):
  1. Gemini 2.5 Flash Image generates the diagram from a structured prompt
     (e.g. 'educational diagram of a plant cell, labeled parts visible').
  2. Gemini 2.5 Pro (vision) looks at the generated image and returns
     pixel-coordinate bounding boxes for each named part.

Output:
  {
    "image_url": "http://localhost:9000/lulia-generated/hotspots/<uuid>.png",
    "image_width": 1024, "image_height": 1024,
    "hotspots": [
      {"label": "nucleus", "x": 234, "y": 156, "w": 80, "h": 80},
      ...
    ],
    "cache_key": "<hash>",  # so callers can dedupe identical requests
  }

Caching: by (subject + sorted parts) hash — so generating the same plant
cell diagram twice reuses the first image. Cached entries live in a new
`hotspot_diagrams` table (one row per unique subject+parts combo).

Failures:
  - Leonardo fails -> return {"error": ...}
  - Vision returns no coordinates -> return image_url + empty hotspots;
    the renderer shows the image without click detection (graceful).
"""
import base64
import hashlib
import io
import json
import logging
import os
import re
from typing import Optional
from uuid import uuid4

log = logging.getLogger(__name__)


def _cache_key(subject: str, parts: list[str]) -> str:
    normalized = subject.strip().lower() + "|" + "|".join(sorted(p.strip().lower() for p in parts))
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _get_cached(cache_key: str) -> Optional[dict]:
    """Return a previously-generated diagram if present, else None."""
    try:
        from src.lms_agents.tools.db import get_connection
        from psycopg2.extras import RealDictCursor
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """SELECT image_url, image_width, image_height, hotspots_json
               FROM hotspot_diagrams WHERE cache_key = %s""",
            (cache_key,),
        )
        row = cur.fetchone()
        cur.close(); conn.close()
        if row:
            return {
                "image_url": row["image_url"],
                "image_width": row["image_width"],
                "image_height": row["image_height"],
                "hotspots": row["hotspots_json"] or [],
                "cache_key": cache_key,
                "cached": True,
            }
    except Exception as e:
        log.warning(f"[HotspotDiagram] Cache read failed (non-fatal): {e}")
    return None


def _save_to_cache(cache_key: str, subject: str, parts: list[str], result: dict):
    try:
        from src.lms_agents.tools.db import get_connection
        from psycopg2.extras import Json
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO hotspot_diagrams
                 (cache_key, subject, parts_json, image_url, image_width,
                  image_height, hotspots_json)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (cache_key) DO NOTHING""",
            (cache_key, subject, Json(parts),
             result["image_url"], result.get("image_width", 1024),
             result.get("image_height", 1024), Json(result.get("hotspots", []))),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        log.warning(f"[HotspotDiagram] Cache write failed (non-fatal): {e}")


def generate_hotspot_diagram(subject: str, parts: list[str]) -> dict:
    """
    Generate a labeled educational diagram with clickable hotspot coordinates.

    Args:
        subject: what to draw — e.g. 'plant cell cross-section',
                 'water cycle', 'digestive system', 'circuit diagram'
        parts: list of labels to locate — e.g. ['nucleus', 'cell wall',
               'chloroplast', 'vacuole', 'cytoplasm']

    Returns:
        {image_url, image_width, image_height, hotspots, cache_key}
        or {"error": "..."}
    """
    subject = (subject or "").strip()
    parts = [p.strip() for p in (parts or []) if p and p.strip()]
    if not subject or not parts:
        return {"error": "subject and parts are required"}

    ck = _cache_key(subject, parts)
    cached = _get_cached(ck)
    if cached:
        log.info(f"[HotspotDiagram] Cache hit for '{subject}' ({ck})")
        return cached

    # Step 1: Generate image via Gemini 2.5 Flash Image
    labels_text = ", ".join(parts)
    prompt = (
        f"Clean educational diagram of a {subject}, science textbook style, "
        f"clearly labeled parts visible: {labels_text}. Each labeled part is "
        f"distinct and identifiable. Neutral white background, professional "
        f"scientific illustration, flat colors, no photorealism, no watermark."
    )
    image_bytes = _generate_image_gemini(prompt)
    if not image_bytes:
        return {"error": "Image generation failed: Gemini returned no image"}

    # Step 2: Upload to MinIO so browsers can fetch it.
    image_id = uuid4().hex
    key = f"hotspots/{image_id}.png"
    image_url = ""
    try:
        import boto3
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        bucket = os.environ.get("S3_BUCKET_GENERATED", "lulia-generated")
        s3.put_object(Bucket=bucket, Key=key, Body=image_bytes, ContentType="image/png")
        endpoint = os.environ.get("S3_PUBLIC_ENDPOINT") or os.environ.get("S3_ENDPOINT", "http://localhost:9000")
        image_url = f"{endpoint}/{bucket}/{key}"
    except Exception as e:
        log.error(f"[HotspotDiagram] MinIO upload failed: {e}")
        return {"error": f"Upload failed: {e}"}

    # Step 3: Ask Gemini 2.5 Pro (vision) for the pixel coordinates of each part
    hotspots = _extract_hotspot_coords(image_bytes, parts)

    result = {
        "image_url": image_url,
        "image_width": 1024,
        "image_height": 1024,
        "hotspots": hotspots,
        "cache_key": ck,
        "cached": False,
    }
    _save_to_cache(ck, subject, parts, result)
    return result


def _gemini_client():
    """Return a configured google.genai Client using GOOGLE_GEMINI_API_KEY."""
    from google import genai
    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def _generate_image_gemini(prompt: str) -> Optional[bytes]:
    """
    Generate an image via Gemini 2.5 Flash Image. Returns the raw bytes of
    the first inline image part, or None if the model returned only text.
    """
    try:
        client = _gemini_client()
        resp = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt],
        )
        for part in (resp.candidates[0].content.parts if resp.candidates else []):
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data
        log.error("[HotspotDiagram] Gemini image gen returned no inline image parts")
        return None
    except Exception as e:
        log.error(f"[HotspotDiagram] Gemini image gen failed: {e}")
        return None


def _extract_hotspot_coords(image_bytes: bytes, parts: list[str]) -> list[dict]:
    """
    Ask Gemini 2.5 Pro (vision) for pixel coordinates of each named part.
    Returns [{label, x, y, w, h}, ...] — empty list on any failure.
    """
    try:
        from google.genai import types
        client = _gemini_client()
    except Exception as e:
        log.warning(f"[HotspotDiagram] Gemini vision unavailable: {e}")
        return []

    # Detect media type from the image bytes' magic signature.
    if image_bytes.startswith(b"\x89PNG"):
        media_type = "image/png"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif image_bytes.startswith(b"GIF8"):
        media_type = "image/gif"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        media_type = "image/webp"
    else:
        media_type = "image/png"

    parts_list = "\n".join(f"  - {p}" for p in parts)
    prompt_text = (
        f"You are annotating a labeled educational diagram so students can "
        f"click on each part. The image is 1024x1024 pixels. For each part "
        f"in this list, return the pixel center and approximate bounding box "
        f"of where it appears in the image:\n\n{parts_list}\n\n"
        f"Coordinate system: origin (0,0) is top-left. x increases rightward, "
        f"y increases downward. Return ONLY valid JSON in this exact shape:\n\n"
        f'{{"hotspots": [{{"label": "<part>", "x": <center_x>, "y": <center_y>, '
        f'"w": <box_width>, "h": <box_height>}}]}}\n\n'
        f"The box should be big enough for a finger-friendly tap target "
        f"(at least 60x60 px), centered on the part. If a part is not "
        f"visible or identifiable, omit it from the response (do not guess). "
        f"No preamble, no markdown — just JSON."
    )

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                prompt_text,
            ],
        )
        text = (resp.text or "").strip()
        # Strip markdown fences if Gemini wrapped its JSON
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            log.warning(f"[HotspotDiagram] Vision returned no JSON: {text[:200]}")
            return []
        data = json.loads(match.group())
        raw = data.get("hotspots", []) or []
        cleaned = []
        for h in raw:
            try:
                label = str(h.get("label", "")).strip()
                x = int(h.get("x", 0))
                y = int(h.get("y", 0))
                w = max(40, int(h.get("w", 80)))
                h_ = max(40, int(h.get("h", 80)))
                if not label:
                    continue
                cleaned.append({"label": label, "x": x, "y": y, "w": w, "h": h_})
            except (TypeError, ValueError):
                continue
        log.info(f"[HotspotDiagram] Vision returned {len(cleaned)} hotspots for {len(parts)} parts")
        return cleaned
    except Exception as e:
        log.error(f"[HotspotDiagram] Vision annotation failed: {e}")
        return []
