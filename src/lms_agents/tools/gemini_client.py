"""
Unified Gemini Client — shared by Slides, Forms, and any future Gemini integrations.

Uses Gemini Flash for content generation. Falls back to Claude Haiku if Gemini fails.
"""
import json
import logging
import os
import re

log = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"


def get_gemini_model(model: str | None = None):
    """Get a configured Gemini GenerativeModel instance."""
    import google.generativeai as genai
    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model or GEMINI_MODEL)


def generate_with_gemini(prompt: str, model: str | None = None) -> str:
    """Call Gemini Flash and return text response."""
    try:
        m = get_gemini_model(model)
        response = m.generate_content(prompt)
        return response.text
    except Exception as e:
        log.error(f"[Gemini] API error: {e}")
        raise


def generate_with_gemini_json(prompt: str, model: str | None = None) -> dict | list:
    """Call Gemini and parse JSON from response."""
    text = generate_with_gemini(prompt, model)
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    return json.loads(text)


def generate_with_fallback(prompt: str, model: str | None = None) -> str:
    """
    Try Gemini first, fall back to Claude Haiku if Gemini fails.
    Returns the text response from whichever provider succeeds.
    """
    try:
        return generate_with_gemini(prompt, model)
    except Exception as e:
        log.warning(f"[Gemini] Failed ({e}), falling back to Claude Haiku")

    # Fallback: Claude Haiku
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Both Gemini and Anthropic API keys are unavailable")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def generate_json_with_fallback(prompt: str, model: str | None = None) -> dict | list:
    """Try Gemini for JSON, fall back to Claude Haiku."""
    text = generate_with_fallback(prompt, model)
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    # Find JSON in response
    for start, end in [("{", "}"), ("[", "]")]:
        idx = text.find(start)
        if idx >= 0:
            depth = 0
            for i in range(idx, len(text)):
                if text[i] == start:
                    depth += 1
                elif text[i] == end:
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[idx:i + 1])
    return json.loads(text)
