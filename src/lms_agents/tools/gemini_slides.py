"""
Gemini Slides — generates Google Slides presentations.

Uses Gemini Flash (via unified client) for content generation,
then Google Slides API for rendering.
"""
import json
import logging
import os

from src.lms_agents.tools.google_auth import get_credentials
from src.lms_agents.tools.gemini_client import generate_json_with_fallback

log = logging.getLogger(__name__)


def generate_slide_content(
    content: dict,
    standards: list[str],
    theme: str = "modern_clean",
    slide_count: int = 8,
) -> list[dict]:
    """
    Use Gemini Flash to generate slide deck content.
    Falls back to Claude Haiku if Gemini is unavailable.
    Returns list of slide dicts: [{title, bullets, speaker_notes}, ...]
    """
    title = content.get("title", "Lesson")
    questions = content.get("questions", [])
    standards_text = ", ".join(standards[:5])

    prompt = f"""Create a Google Slides presentation for this educational content.

Title: {title}
Standards: {standards_text}
Content: {json.dumps(questions[:10], indent=2)}
Number of slides: {slide_count}

Generate {slide_count} slides as a JSON array:
[
  {{"title": "slide title", "bullets": ["bullet 1", "bullet 2", "bullet 3"], "speaker_notes": "what the teacher should say"}}
]

Include:
1. Title slide with the lesson title and standards
2. Learning objectives (2-3 clear objectives)
3-{slide_count - 2}. Content slides (one key concept per slide, use examples)
{slide_count - 1}. Practice problems slide
{slide_count}. Summary / Exit ticket slide

Make bullets concise (max 10 words each). Speaker notes should be 2-3 sentences.
Respond with ONLY the JSON array."""

    try:
        result = generate_json_with_fallback(prompt)
        if isinstance(result, list) and len(result) > 0:
            log.info(f"[Slides] Generated {len(result)} slides via Gemini/fallback")
            return result
    except Exception as e:
        log.warning(f"[Slides] Content generation failed: {e}")

    return _fallback_slides(content, standards)


def _fallback_slides(content: dict, standards: list[str]) -> list[dict]:
    """Static fallback when all LLMs are unavailable."""
    title = content.get("title", "Lesson")
    questions = content.get("questions", [])
    return [
        {"title": title, "bullets": [f"Standards: {', '.join(standards[:3])}"], "speaker_notes": "Welcome to today's lesson."},
        {"title": "Learning Objectives", "bullets": ["Understand key concepts", "Apply to practice problems", "Demonstrate mastery"], "speaker_notes": "By the end of this lesson, students will be able to accomplish these objectives."},
        {"title": "Key Concepts", "bullets": [q.get("question_text", "")[:60] for q in questions[:4]], "speaker_notes": "Let's explore the main ideas for today."},
        {"title": "Practice", "bullets": [q.get("question_text", "")[:60] for q in questions[4:8]], "speaker_notes": "Now let's practice what we've learned."},
        {"title": "Summary", "bullets": ["Review what we learned", "Complete the exit ticket", "Ask questions if needed"], "speaker_notes": "Great work today! Let's wrap up."},
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

    presentation = slides_service.presentations().create(body={"title": title}).execute()
    pres_id = presentation["presentationId"]

    requests = []
    for i in range(1, len(slides_content)):
        requests.append({
            "createSlide": {
                "objectId": f"slide_{i}",
                "insertionIndex": i,
                "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"},
            }
        })

    if requests:
        slides_service.presentations().batchUpdate(presentationId=pres_id, body={"requests": requests}).execute()

    updated_pres = slides_service.presentations().get(presentationId=pres_id).execute()
    text_requests = []

    for i, slide in enumerate(slides_content):
        if i >= len(updated_pres.get("slides", [])):
            break
        for elem in updated_pres["slides"][i].get("pageElements", []):
            ph_type = elem.get("shape", {}).get("placeholder", {}).get("type", "")
            if ph_type in ("TITLE", "CENTERED_TITLE"):
                text_requests.append({"insertText": {"objectId": elem["objectId"], "text": slide.get("title", "")}})
            elif ph_type in ("BODY", "SUBTITLE"):
                text_requests.append({"insertText": {"objectId": elem["objectId"], "text": "\n".join(f"• {b}" for b in slide.get("bullets", []))}})

    if text_requests:
        slides_service.presentations().batchUpdate(presentationId=pres_id, body={"requests": text_requests}).execute()

    url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
    log.info(f"[Slides] Created: {url}")
    return {"presentation_id": pres_id, "url": url}
