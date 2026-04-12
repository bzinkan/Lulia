"""
Imagen 3 image generation via Google Vertex AI.

Used by the Short Clips preview flow: teacher enters a prompt, we generate
4 cheap still images (~$0.04 each) so they can pick the visual style before
committing to an expensive Veo video generation.

The chosen preview image can be passed back to Veo as a reference frame for
style/composition consistency.

Env vars (shared with veo_generator.py):
  GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_REGION, GOOGLE_APPLICATION_CREDENTIALS
  IMAGEN_MODEL_ID (default: "imagen-3.0-generate-002")
"""
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_MODEL = "imagen-3.0-generate-002"


def generate_previews(prompt: str, count: int = 4, aspect_ratio: str = "16:9") -> dict:
    """
    Generate preview still images from a text prompt.

    Args:
        prompt: Scene description.
        count: Number of images to generate (1-8). Default 4.
        aspect_ratio: "16:9" matches the default Veo clip ratio.

    Returns:
        {"success": True, "images": [uri1, uri2, ...]}
    or {"success": False, "error": str}
    """
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

    model_id = os.environ.get("IMAGEN_MODEL_ID", DEFAULT_MODEL)
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
        return {"success": True, "images": images, "model": model_id}
    except Exception as e:
        log.error(f"[Imagen] Preview generation failed: {e}")
        return {"success": False, "error": str(e)}


def estimate_cost_usd(count: int = 4) -> float:
    """Approximate Imagen 3 cost per preview set."""
    return count * 0.04
