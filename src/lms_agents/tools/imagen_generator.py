"""
Clip preview image generation.

Originally used Google Imagen 3 via Vertex AI. Now routes through Leonardo.ai
by default (Phoenix 1.0 — ~10x cheaper at similar quality) with Imagen 3 as
a fallback.

Used by the Short Clips preview flow: teacher enters a prompt, we generate
4 cheap still images so they can pick the visual style before committing to
an expensive Veo video generation.

The chosen preview image can be passed back to Veo as a reference frame for
style/composition consistency.

Env vars:
  LEONARDO.AI_API_KEY          (primary provider)
  GOOGLE_CLOUD_PROJECT         (fallback)
  GOOGLE_CLOUD_REGION          (fallback, default: us-central1)
  GOOGLE_APPLICATION_CREDENTIALS
  IMAGEN_PREVIEW_PROVIDER      ("leonardo" | "imagen" — default: leonardo)
  IMAGEN_MODEL_ID              (default: "imagen-3.0-generate-002")
"""
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_IMAGEN_MODEL = "imagen-3.0-generate-002"


def generate_previews(prompt: str, count: int = 4, aspect_ratio: str = "16:9") -> dict:
    """
    Generate preview still images from a text prompt.

    Args:
        prompt: Scene description.
        count: Number of images to generate (1-8). Default 4.
        aspect_ratio: "16:9" matches the default Veo clip ratio.

    Returns:
        {"success": True, "images": [uri, ...], "model": str, "provider": str}
    or {"success": False, "error": str}
    """
    preferred = os.environ.get("IMAGEN_PREVIEW_PROVIDER", "leonardo").lower()

    if preferred == "leonardo":
        result = _generate_via_leonardo(prompt, count, aspect_ratio)
        if result.get("success"):
            return result
        log.warning(f"[Previews] Leonardo failed, falling back to Imagen: {result.get('error')}")

    imagen_result = _generate_via_imagen(prompt, count, aspect_ratio)
    if imagen_result.get("success") or preferred == "imagen":
        return imagen_result

    # Both failed — return the richer error
    return {"success": False, "error": f"All providers failed. Leonardo error reported above; Imagen: {imagen_result.get('error')}"}


def _generate_via_leonardo(prompt: str, count: int, aspect_ratio: str) -> dict:
    """Primary path — Leonardo Phoenix 1.0."""
    from src.lms_agents.tools.leonardo_client import generate_images

    result = generate_images(
        prompt=prompt,
        count=count,
        aspect_ratio=aspect_ratio,
    )
    if result.get("success"):
        return {
            "success": True,
            "images": result["images"],
            "model": result.get("model", "leonardo-phoenix"),
            "provider": "leonardo",
            "image_ids": result.get("image_ids", []),
            "generation_id": result.get("generation_id"),
        }
    return result


def _generate_via_imagen(prompt: str, count: int, aspect_ratio: str) -> dict:
    """Fallback path — Google Imagen 3 via Vertex AI."""
    try:
        from google import genai
        from google.genai.types import GenerateImagesConfig
    except ImportError as e:
        return {
            "success": False,
            "error": "google-genai package not installed.",
            "details": str(e),
        }

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    region = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    if not project:
        return {"success": False, "error": "GOOGLE_CLOUD_PROJECT env var not set"}

    model_id = os.environ.get("IMAGEN_MODEL_ID", DEFAULT_IMAGEN_MODEL)
    client = genai.Client(vertexai=True, project=project, location=region)

    try:
        response = client.models.generate_images(
            model=model_id,
            prompt=prompt,
            config=GenerateImagesConfig(
                number_of_images=max(1, min(count, 8)),
                aspect_ratio=aspect_ratio,
            ),
        )
        images = []
        for img in (response.generated_images or []):
            uri = getattr(img.image, "uri", None) or getattr(img.image, "image_bytes", None)
            if uri:
                images.append(uri)
        if not images:
            return {"success": False, "error": "Imagen returned no images"}
        return {"success": True, "images": images, "model": model_id, "provider": "imagen"}
    except Exception as e:
        log.error(f"[Imagen] Preview generation failed: {e}")
        return {"success": False, "error": str(e)}


def estimate_cost_usd(count: int = 4) -> float:
    """
    Approximate cost per preview set.

    Leonardo Phoenix: ~$0.004/image × 4 = $0.016
    Imagen 3 (fallback): ~$0.04/image × 4 = $0.16
    """
    provider = os.environ.get("IMAGEN_PREVIEW_PROVIDER", "leonardo").lower()
    per_image = 0.004 if provider == "leonardo" else 0.04
    return count * per_image
