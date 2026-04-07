"""
Image Generator — generates images via Gemini (primary) or Replicate Flux (fallback).

Uses Gemini's native image generation for educational illustrations.
Falls back to Replicate Flux if Gemini is unavailable.
"""
import base64
import logging
import os
import tempfile

log = logging.getLogger(__name__)


def generate_image(
    prompt: str,
    output_path: str | None = None,
    width: int = 1024,
    height: int = 1024,
) -> str | None:
    """
    Generate an image. Tries Gemini first, falls back to Replicate Flux.

    Returns: path to downloaded image, or None on failure.
    """
    # Try Gemini first
    path = _generate_with_gemini(prompt, output_path)
    if path:
        return path

    # Fallback to Replicate
    log.info("[ImageGen] Gemini failed or unavailable, trying Replicate Flux")
    return _generate_with_replicate(prompt, output_path, width, height)


def _generate_with_gemini(prompt: str, output_path: str | None = None) -> str | None:
    """Generate an image using Gemini's native image generation."""
    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        log.warning("[ImageGen] GOOGLE_GEMINI_API_KEY not set")
        return None

    # Try the new google-genai SDK first, fall back to REST API
    path = _gemini_new_sdk(api_key, prompt, output_path)
    if path:
        return path
    return _gemini_rest_api(api_key, prompt, output_path)


def _gemini_new_sdk(api_key: str, prompt: str, output_path: str | None) -> str | None:
    """Try using the new google-genai SDK (if installed)."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            return None

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                if not output_path:
                    output_path = tempfile.mktemp(suffix=".png")
                with open(output_path, "wb") as f:
                    f.write(part.inline_data.data)
                log.info(f"[ImageGen] Gemini (new SDK) generated image: {output_path}")
                return output_path
        return None
    except ImportError:
        log.info("[ImageGen] google-genai SDK not installed, trying REST API")
        return None
    except Exception as e:
        log.warning(f"[ImageGen] Gemini new SDK failed: {e}")
        return None


def _gemini_rest_api(api_key: str, prompt: str, output_path: str | None) -> str | None:
    """Use Gemini REST API directly for image generation (works with any SDK version)."""
    try:
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }

        resp = httpx.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            log.warning("[ImageGen] Gemini REST returned no candidates")
            return None

        for part in candidates[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData", {})
            if inline.get("mimeType", "").startswith("image/"):
                image_bytes = base64.b64decode(inline["data"])
                if not output_path:
                    output_path = tempfile.mktemp(suffix=".png")
                with open(output_path, "wb") as f:
                    f.write(image_bytes)
                log.info(f"[ImageGen] Gemini (REST) generated image: {output_path}")
                return output_path

        log.warning("[ImageGen] Gemini REST response had no image parts")
        return None

    except Exception as e:
        log.error(f"[ImageGen] Gemini REST API failed: {e}")
        return None


def _generate_with_replicate(
    prompt: str,
    output_path: str | None = None,
    width: int = 1024,
    height: int = 1024,
) -> str | None:
    """Fallback: generate an image using Replicate's Flux 1.1 Pro."""
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        log.warning("[ImageGen] REPLICATE_API_TOKEN not set — image generation skipped")
        return None

    try:
        import httpx
        import replicate

        output = replicate.run(
            "black-forest-labs/flux-1.1-pro",
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

        if not output_path:
            output_path = tempfile.mktemp(suffix=".png")

        resp = httpx.get(image_url, follow_redirects=True, timeout=60)
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(resp.content)

        log.info(f"[ImageGen] Replicate generated image: {output_path}")
        return output_path

    except Exception as e:
        log.error(f"[ImageGen] Replicate generation failed: {e}")
        return None
