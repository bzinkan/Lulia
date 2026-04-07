"""
Image Generator — generates images via Replicate (Flux 1.1 Pro).

Used for Lulings character generation and future illustration needs.
"""
import logging
import os
import tempfile

import httpx

log = logging.getLogger(__name__)


def generate_image(
    prompt: str,
    output_path: str | None = None,
    model: str = "black-forest-labs/flux-1.1-pro",
    width: int = 1024,
    height: int = 1024,
) -> str | None:
    """
    Generate an image using Replicate's API.

    Args:
        prompt: text description of the image
        output_path: where to save the file (temp file if None)
        model: Replicate model ID
        width/height: image dimensions

    Returns: path to downloaded image, or None on failure.
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        log.warning("REPLICATE_API_TOKEN not set — image generation skipped")
        return None

    try:
        import replicate

        output = replicate.run(
            model,
            input={
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_outputs": 1,
                "output_format": "png",
            },
        )

        # output is a list of URLs or FileOutput objects
        image_url = None
        if isinstance(output, list) and output:
            item = output[0]
            image_url = str(item) if hasattr(item, '__str__') else item
        elif hasattr(output, 'url'):
            image_url = output.url
        else:
            image_url = str(output)

        if not image_url:
            log.error("[ImageGen] No output URL from Replicate")
            return None

        # Download the image
        if not output_path:
            output_path = tempfile.mktemp(suffix=".png")

        resp = httpx.get(image_url, follow_redirects=True, timeout=60)
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(resp.content)

        log.info(f"[ImageGen] Generated image: {output_path}")
        return output_path

    except Exception as e:
        log.error(f"[ImageGen] Generation failed: {e}")
        return None
