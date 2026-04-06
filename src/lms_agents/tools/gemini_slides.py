"""
Gemini Slides — generates Google Slides presentations using Gemini Flash
for content and the Slides API for rendering.
"""
import json
import logging
import os
import re

from src.lms_agents.tools.google_auth import get_credentials

log = logging.getLogger(__name__)


def generate_slide_content(content: dict, standards: list[str], theme: str = "modern_clean") -> list[dict]:
    """
    Use Gemini Flash to generate slide deck content.
    Returns list of slide dicts: [{title, bullets, speaker_notes}, ...]
    """
    import google.generativeai as genai

    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        log.warning("GOOGLE_GEMINI_API_KEY not set")
        return _fallback_slides(content, standards)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    title = content.get("title", "Lesson")
    questions = content.get("questions", [])
    standards_text = ", ".join(standards[:5])

    prompt = f"""Create a Google Slides presentation for this educational content:

Title: {title}
Standards: {standards_text}
Content: {json.dumps(questions[:10], indent=2)}

Generate 6-10 slides as a JSON array:
[
  {{"title": "slide title", "bullets": ["bullet 1", "bullet 2"], "speaker_notes": "what to say"}},
  ...
]

Include:
1. Title slide with standards
2. Learning objectives
3-6. Content slides (one concept per slide)
7. Practice problems slide
8. Summary/Exit ticket slide

Respond with ONLY the JSON array."""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        log.warning(f"Gemini slide generation failed: {e}")

    return _fallback_slides(content, standards)


def _fallback_slides(content: dict, standards: list[str]) -> list[dict]:
    """Fallback slide content when Gemini is unavailable."""
    title = content.get("title", "Lesson")
    questions = content.get("questions", [])
    return [
        {"title": title, "bullets": [f"Standards: {', '.join(standards[:3])}"], "speaker_notes": "Welcome"},
        {"title": "Learning Objectives", "bullets": ["Understand key concepts", "Apply to practice problems"], "speaker_notes": ""},
        {"title": "Key Concepts", "bullets": [q.get("question_text", "")[:80] for q in questions[:4]], "speaker_notes": ""},
        {"title": "Practice", "bullets": [q.get("question_text", "")[:80] for q in questions[4:8]], "speaker_notes": ""},
        {"title": "Summary", "bullets": ["Review what we learned", "Complete exit ticket"], "speaker_notes": ""},
    ]


def create_google_slides(teacher_id: str, slides_content: list[dict], title: str) -> dict:
    """
    Create a Google Slides presentation using the Slides API.
    Returns {presentation_id, url}.
    """
    credentials = get_credentials(teacher_id)
    if not credentials:
        raise ValueError("Teacher not connected to Google")

    from googleapiclient.discovery import build

    slides_service = build("slides", "v1", credentials=credentials)

    # Create blank presentation
    presentation = slides_service.presentations().create(
        body={"title": title}
    ).execute()
    pres_id = presentation["presentationId"]

    # Add slides
    requests = []
    for i, slide in enumerate(slides_content):
        if i == 0:
            # Use the default first slide
            page_id = presentation["slides"][0]["objectId"]
        else:
            page_id = f"slide_{i}"
            requests.append({
                "createSlide": {
                    "objectId": page_id,
                    "insertionIndex": i,
                    "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"},
                }
            })

    if requests:
        slides_service.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": requests}
        ).execute()

    # Add text content to each slide
    updated_pres = slides_service.presentations().get(presentationId=pres_id).execute()
    text_requests = []

    for i, slide in enumerate(slides_content):
        if i >= len(updated_pres.get("slides", [])):
            break
        page = updated_pres["slides"][i]
        elements = page.get("pageElements", [])

        for elem in elements:
            shape = elem.get("shape", {})
            placeholder = shape.get("placeholder", {})
            ph_type = placeholder.get("type", "")

            if ph_type in ("TITLE", "CENTERED_TITLE"):
                text_requests.append({
                    "insertText": {
                        "objectId": elem["objectId"],
                        "text": slide.get("title", ""),
                    }
                })
            elif ph_type in ("BODY", "SUBTITLE"):
                bullets = slide.get("bullets", [])
                text = "\n".join(f"• {b}" for b in bullets)
                text_requests.append({
                    "insertText": {
                        "objectId": elem["objectId"],
                        "text": text,
                    }
                })

    if text_requests:
        slides_service.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": text_requests}
        ).execute()

    url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
    log.info(f"[Slides] Created presentation: {url}")
    return {"presentation_id": pres_id, "url": url}
