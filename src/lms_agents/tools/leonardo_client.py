"""
Leonardo.ai API client — image generation, motion (image-to-video), inpainting.

Covers multiple lulia use cases:
  - Cheap preview thumbnails for Short Clips (replaces Imagen)
  - Classroom illustrations for worksheets / flashcards / task cards
  - Character-consistent Luling generations (via image guidance)
  - Image-to-video fallback when Veo 3 Fast fails (Motion 2.0)
  - In-app image editing (inpaint/outpaint — phase 2)

Env vars:
  LEONARDO.AI_API_KEY          (required — note the period, matches .env.development)
  LEONARDO_MODEL_ID            (optional, default: Phoenix 1.0)
  LEONARDO_POLL_TIMEOUT_SEC    (optional, default: 60)
  LEONARDO_POLL_INTERVAL_SEC   (optional, default: 2)

Public API:
  generate_images(prompt, count, width, height, **opts) -> dict
  get_generation(generation_id) -> dict
  generate_motion(image_id) -> dict           (phase 2)
  inpaint(image_id, mask_url, prompt) -> dict (phase 2)
"""
import logging
import os
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"

# Known model IDs (https://docs.leonardo.ai/reference/platform-models)
MODEL_PHOENIX = "6b645e3a-d64f-4341-a6d8-7a3690fbf042"   # Phoenix 1.0 — balanced
MODEL_LIGHTNING_XL = "b24e16ff-06e3-43eb-8d33-4416c2d75876"  # ultra fast, cheap
MODEL_FLUX_DEV = "b2614463-296c-462a-9586-aafdb8f00e36"  # high quality

DEFAULT_MODEL = os.environ.get("LEONARDO_MODEL_ID", MODEL_PHOENIX)
DEFAULT_TIMEOUT_SEC = int(os.environ.get("LEONARDO_POLL_TIMEOUT_SEC", "60"))
DEFAULT_INTERVAL_SEC = float(os.environ.get("LEONARDO_POLL_INTERVAL_SEC", "2"))


def _api_key() -> Optional[str]:
    # The .env.development file uses "LEONARDO.AI_API_KEY" (with the period)
    return (
        os.environ.get("LEONARDO.AI_API_KEY")
        or os.environ.get("LEONARDO_API_KEY")
    )


def _headers() -> dict:
    key = _api_key()
    if not key:
        raise RuntimeError("LEONARDO.AI_API_KEY not set")
    return {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _dims_for_aspect_ratio(aspect_ratio: str, base: int = 1024) -> tuple[int, int]:
    """Convert an aspect ratio string to width/height in multiples of 8."""
    ratios = {
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "4:3":  (1024, 768),
        "3:4":  (768, 1024),
        "1:1":  (768, 768),
    }
    return ratios.get(aspect_ratio, (1024, 576))


def generate_images(
    prompt: str,
    count: int = 4,
    width: Optional[int] = None,
    height: Optional[int] = None,
    aspect_ratio: str = "16:9",
    model_id: Optional[str] = None,
    preset_style: Optional[str] = None,
    transparent: bool = False,
    reference_image_id: Optional[str] = None,
    reference_strength: str = "Mid",  # "Low" | "Mid" | "High"
    negative_prompt: Optional[str] = None,
) -> dict:
    """
    Generate N images from a prompt. Polls until complete, returns URLs.

    Returns:
      {"success": True, "images": [url, ...], "generation_id": str, "model": str}
    or {"success": False, "error": str}
    """
    if not _api_key():
        return {"success": False, "error": "LEONARDO.AI_API_KEY not set"}

    w, h = (width, height) if width and height else _dims_for_aspect_ratio(aspect_ratio)
    model = model_id or DEFAULT_MODEL

    body = {
        "prompt": prompt,
        "modelId": model,
        "num_images": max(1, min(count, 8)),
        "width": w,
        "height": h,
    }
    if preset_style:
        body["presetStyle"] = preset_style
    if transparent:
        body["transparency"] = "foreground_only"
    if negative_prompt:
        body["negative_prompt"] = negative_prompt
    if reference_image_id:
        body["controlnets"] = [{
            "initImageId": reference_image_id,
            "initImageType": "UPLOADED",
            "preprocessorId": 67,  # Character Reference
            "strengthType": reference_strength,
        }]

    try:
        with httpx.Client(timeout=30.0) as client:
            # Kick off generation
            r = client.post(f"{BASE_URL}/generations", json=body, headers=_headers())
            if r.status_code != 200:
                log.error(f"[Leonardo] generations POST failed: {r.status_code} {r.text[:300]}")
                return {"success": False, "error": f"Leonardo API {r.status_code}: {r.text[:200]}"}

            job = r.json().get("sdGenerationJob") or {}
            generation_id = job.get("generationId")
            if not generation_id:
                return {"success": False, "error": "No generationId returned"}

            # Poll until complete
            deadline = time.time() + DEFAULT_TIMEOUT_SEC
            while time.time() < deadline:
                time.sleep(DEFAULT_INTERVAL_SEC)
                poll = client.get(f"{BASE_URL}/generations/{generation_id}", headers=_headers())
                if poll.status_code != 200:
                    log.warning(f"[Leonardo] poll status {poll.status_code}, retrying")
                    continue
                gen = poll.json().get("generations_by_pk") or {}
                status = gen.get("status")
                if status == "COMPLETE":
                    images = [
                        {"url": img["url"], "id": img["id"]}
                        for img in gen.get("generated_images", [])
                        if img.get("url")
                    ]
                    if not images:
                        return {"success": False, "error": "Leonardo returned no images"}
                    return {
                        "success": True,
                        "images": [i["url"] for i in images],
                        "image_ids": [i["id"] for i in images],
                        "generation_id": generation_id,
                        "model": model,
                    }
                if status == "FAILED":
                    return {"success": False, "error": "Leonardo generation FAILED"}
                # PENDING — keep polling

            return {"success": False, "error": f"Leonardo generation timed out after {DEFAULT_TIMEOUT_SEC}s"}

    except httpx.HTTPError as e:
        log.error(f"[Leonardo] HTTP error: {e}")
        return {"success": False, "error": f"Network error: {e}"}
    except Exception as e:
        log.error(f"[Leonardo] Unexpected error: {e}")
        return {"success": False, "error": str(e)}


def get_generation(generation_id: str) -> dict:
    """Fetch the status/results of a single generation by ID."""
    if not _api_key():
        return {"success": False, "error": "LEONARDO.AI_API_KEY not set"}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{BASE_URL}/generations/{generation_id}", headers=_headers())
            if r.status_code != 200:
                return {"success": False, "error": f"Leonardo API {r.status_code}"}
            gen = r.json().get("generations_by_pk") or {}
            return {"success": True, "status": gen.get("status"), "generation": gen}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_init_image(image_bytes: bytes, extension: str = "png") -> dict:
    """
    Upload an image to Leonardo so it can be used as a reference or inpaint base.

    Returns:
      {"success": True, "image_id": str}
    or {"success": False, "error": str}

    Leonardo's upload flow is a two-step presigned POST:
      1. POST /init-image {extension} -> {id, url, fields}
      2. POST to S3 url with multipart form (fields + image) -> image is stored
    """
    if not _api_key():
        return {"success": False, "error": "LEONARDO.AI_API_KEY not set"}

    ext = extension.lower().lstrip(".")
    if ext not in ("png", "jpg", "jpeg", "webp"):
        return {"success": False, "error": f"Unsupported extension: {ext}"}

    try:
        import json as _json
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{BASE_URL}/init-image",
                json={"extension": ext},
                headers=_headers(),
            )
            if r.status_code != 200:
                log.error(f"[Leonardo] init-image failed: {r.status_code} {r.text[:300]}")
                return {"success": False, "error": f"Leonardo init-image {r.status_code}"}

            upload = r.json().get("uploadInitImage") or {}
            image_id = upload.get("id")
            upload_url = upload.get("url")
            fields_raw = upload.get("fields")  # returned as JSON string
            if not (image_id and upload_url and fields_raw):
                return {"success": False, "error": "init-image response missing required fields"}

            fields = _json.loads(fields_raw) if isinstance(fields_raw, str) else fields_raw
            # S3 presigned POST — fields go first, then file last
            content_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
            files = {"file": (f"upload.{ext}", image_bytes, content_type)}
            s3_resp = client.post(upload_url, data=fields, files=files)
            if s3_resp.status_code not in (200, 201, 204):
                log.error(f"[Leonardo] S3 upload failed: {s3_resp.status_code} {s3_resp.text[:300]}")
                return {"success": False, "error": f"S3 upload {s3_resp.status_code}"}

            return {"success": True, "image_id": image_id}

    except Exception as e:
        log.error(f"[Leonardo] upload_init_image error: {e}")
        return {"success": False, "error": str(e)}


def inpaint(
    init_image_id: str,
    mask_image_id: str,
    prompt: str,
    model_id: Optional[str] = None,
    width: int = 1024,
    height: int = 576,
    num_images: int = 1,
    guidance_scale: int = 7,
) -> dict:
    """
    Run a Canvas inpaint generation. Both init and mask images must already be
    uploaded via upload_init_image(). Mask PNG should be white where the teacher
    wants to change, black elsewhere.

    Returns:
      {"success": True, "images": [url, ...], "generation_id": str}
    or {"success": False, "error": str}
    """
    if not _api_key():
        return {"success": False, "error": "LEONARDO.AI_API_KEY not set"}

    model = model_id or DEFAULT_MODEL

    body = {
        "canvasRequestType": "INPAINT",
        "canvasRequest": True,
        "canvasInitId": init_image_id,
        "canvasMaskId": mask_image_id,
        "prompt": prompt,
        "modelId": model,
        "num_images": max(1, min(num_images, 4)),
        "width": width,
        "height": height,
        "guidance_scale": guidance_scale,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{BASE_URL}/generations-lcm",
                json=body,
                headers=_headers(),
            )
            # Leonardo's canvas generations endpoint historically lived at a few
            # different paths; fall back to the standard /generations if the LCM
            # path returns 404 on this account tier.
            if r.status_code == 404:
                r = client.post(f"{BASE_URL}/generations", json=body, headers=_headers())

            if r.status_code != 200:
                log.error(f"[Leonardo] inpaint POST failed: {r.status_code} {r.text[:300]}")
                return {"success": False, "error": f"Leonardo API {r.status_code}: {r.text[:200]}"}

            payload = r.json()
            job = payload.get("sdGenerationJob") or payload.get("lcmGenerationJob") or {}
            generation_id = job.get("generationId")

            # Some LCM responses return images synchronously
            if "imageDataUrl" in payload or "generated_images" in payload:
                urls = payload.get("imageDataUrl") or [
                    img.get("url") for img in (payload.get("generated_images") or []) if img.get("url")
                ]
                if isinstance(urls, str):
                    urls = [urls]
                if urls:
                    return {"success": True, "images": urls, "generation_id": generation_id}

            if not generation_id:
                return {"success": False, "error": "No generationId returned"}

            # Poll like a normal generation
            deadline = time.time() + DEFAULT_TIMEOUT_SEC
            while time.time() < deadline:
                time.sleep(DEFAULT_INTERVAL_SEC)
                poll = client.get(f"{BASE_URL}/generations/{generation_id}", headers=_headers())
                if poll.status_code != 200:
                    continue
                gen = poll.json().get("generations_by_pk") or {}
                status = gen.get("status")
                if status == "COMPLETE":
                    urls = [img["url"] for img in gen.get("generated_images", []) if img.get("url")]
                    if not urls:
                        return {"success": False, "error": "Leonardo returned no images"}
                    return {"success": True, "images": urls, "generation_id": generation_id}
                if status == "FAILED":
                    return {"success": False, "error": "Leonardo inpaint FAILED"}

            return {"success": False, "error": f"Inpaint timed out after {DEFAULT_TIMEOUT_SEC}s"}

    except Exception as e:
        log.error(f"[Leonardo] inpaint error: {e}")
        return {"success": False, "error": str(e)}


def estimate_image_cost_usd(count: int = 4) -> float:
    """Approximate Leonardo Phoenix cost per image set (~$0.004/image at current rates)."""
    return count * 0.004
