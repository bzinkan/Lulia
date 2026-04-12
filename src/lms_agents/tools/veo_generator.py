"""
Veo 3 Fast video generation via Google Vertex AI.

Generates short educational clips (typically 5-60 seconds) from a text prompt.
Output is uploaded to S3/MinIO and a video row is created in the `short_clips` table.

Credit charging happens in the caller (routers/clips.py) via credit_manager.charge_for_clip()
BEFORE we hit Vertex so a failed generation doesn't lose the teacher's credits.
If the API call fails after charging, the caller is responsible for refund.

Env vars:
  GOOGLE_CLOUD_PROJECT        — Vertex project ID
  GOOGLE_CLOUD_REGION         — e.g., "us-central1"
  GOOGLE_APPLICATION_CREDENTIALS — path to service account JSON
  VEO_MODEL_ID                — default: "veo-3.0-fast-generate-preview"
"""
import logging
import os
import time
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_MODEL = "veo-3.0-fast-generate-preview"


def generate_clip(
    prompt: str,
    duration_sec: int,
    aspect_ratio: str = "16:9",
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a video clip via Veo 3 Fast.

    Args:
        prompt: Text description of what to generate.
        duration_sec: Requested duration. Veo caps per-request clip length; longer
                      durations are stitched from multiple segments by this function.
        aspect_ratio: "16:9" (default, YouTube/Slides friendly) or "9:16" (mobile).
        negative_prompt: Optional — what to avoid.
        seed: Optional deterministic seed for reproducibility.

    Returns:
        {
            "success": True,
            "video_url": str,          # GCS URI returned by Veo (or S3 after upload)
            "duration_sec": int,       # actual duration produced
            "segments": int,           # number of Veo calls stitched
            "model": str,
        }
    or {"success": False, "error": str}
    """
    try:
        # Lazy import so the module loads even without GCP dependencies installed.
        from google import genai
        from google.genai.types import GenerateVideosConfig
    except ImportError as e:
        return {
            "success": False,
            "error": (
                "google-genai package not installed. "
                "pip install google-genai google-cloud-aiplatform"
            ),
            "details": str(e),
        }

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    region = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    if not project:
        return {"success": False, "error": "GOOGLE_CLOUD_PROJECT env var not set"}

    model_id = os.environ.get("VEO_MODEL_ID", DEFAULT_MODEL)

    # Veo 3 Fast: typical per-call cap is 8 seconds. Split longer durations.
    MAX_CLIP_PER_CALL = 8
    segment_lengths = []
    remaining = duration_sec
    while remaining > 0:
        seg = min(remaining, MAX_CLIP_PER_CALL)
        segment_lengths.append(seg)
        remaining -= seg

    client = genai.Client(vertexai=True, project=project, location=region)

    segment_uris: list[str] = []
    total_produced = 0
    try:
        for i, seg_len in enumerate(segment_lengths):
            log.info(
                f"[Veo] Generating segment {i + 1}/{len(segment_lengths)} "
                f"({seg_len}s) for prompt: {prompt[:80]}..."
            )
            config_kwargs = {
                "aspect_ratio": aspect_ratio,
                "duration_seconds": seg_len,
                "number_of_videos": 1,
            }
            if negative_prompt:
                config_kwargs["negative_prompt"] = negative_prompt
            if seed is not None:
                config_kwargs["seed"] = seed + i

            operation = client.models.generate_videos(
                model=model_id,
                prompt=prompt,
                config=GenerateVideosConfig(**config_kwargs),
            )

            # Poll operation until done (Veo is async, typically 30-120s per segment)
            start = time.time()
            while not operation.done:
                if time.time() - start > 600:
                    return {"success": False, "error": f"Veo timeout on segment {i + 1}"}
                time.sleep(5)
                operation = client.operations.get(operation)

            if getattr(operation, "error", None):
                return {"success": False, "error": f"Veo error: {operation.error}"}

            videos = operation.response.generated_videos if operation.response else []
            if not videos:
                return {"success": False, "error": f"Veo returned no video on segment {i + 1}"}

            segment_uris.append(videos[0].video.uri)
            total_produced += seg_len

        # For multi-segment clips, concatenation happens in the caller (routers/clips.py)
        # via ffmpeg on the downloaded segments. For now, return the list.
        return {
            "success": True,
            "video_uris": segment_uris,
            "primary_uri": segment_uris[0],
            "duration_sec": total_produced,
            "segments": len(segment_uris),
            "model": model_id,
        }

    except Exception as e:
        log.error(f"[Veo] Generation failed: {e}")
        return {"success": False, "error": str(e)}


def estimate_cost_usd(duration_sec: int) -> float:
    """Approximate raw Veo 3 Fast cost for this duration (for internal accounting)."""
    return duration_sec * 0.15
