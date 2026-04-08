"""Google Slides + Forms generation routes."""
import logging
import os
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/google", tags=["Google Generate"])
log = logging.getLogger(__name__)

TEACHER_ID = "00000000-0000-0000-0000-000000000001"


class GenerateSlidesRequest(BaseModel):
    topic: str
    grade: str = "4"
    subject: str = "Mathematics"
    slide_count: int = 8
    teacher_id: str = TEACHER_ID


class GenerateFormsRequest(BaseModel):
    topic: str
    grade: str = "4"
    subject: str = "Mathematics"
    question_count: int = 10
    question_types: list[str] = ["multiple_choice", "short_answer"]
    teacher_id: str = TEACHER_ID


@router.post("/slides/generate")
async def generate_slides(req: GenerateSlidesRequest):
    """Generate a Google Slides presentation using Gemini + Slides API."""
    from src.lms_agents.tools.gemini_slides import generate_slide_content, create_google_slides

    try:
        # 1. Generate slide content via Gemini
        # generate_slide_content expects: content (dict with title, questions), standards, theme, slide_count
        content_dict = {
            "title": f"{req.topic} — Grade {req.grade} {req.subject}",
            "questions": [],  # No pre-existing questions — Gemini generates from topic
        }
        slide_content = generate_slide_content(
            content=content_dict,
            standards=[],
            theme="modern_clean",
            slide_count=req.slide_count,
        )

        if not slide_content:
            return {"error": "Failed to generate slide content. Check Gemini API key."}

        # 2. Create Google Slides presentation
        # create_google_slides expects: teacher_id, slides_content (list), title
        title = f"{req.topic} — Grade {req.grade} {req.subject}"
        result = create_google_slides(
            teacher_id=req.teacher_id,
            slides_content=slide_content,
            title=title,
        )

        if not result:
            return {"error": "Failed to create Google Slides. Is your Google account connected? Go to Settings → Google Classroom to connect."}

        return {
            "slides_url": result.get("url", result.get("presentation_url", "")),
            "presentation_id": result.get("presentation_id", ""),
            "title": title,
            "slide_count": len(slide_content) if isinstance(slide_content, list) else req.slide_count,
            "status": "complete",
        }

    except ValueError as e:
        # Google auth not connected
        return {"error": f"Google account not connected. Go to Settings → Google Classroom to connect. ({e})"}
    except Exception as e:
        log.error(f"[Slides] Generation failed: {e}")
        return {"error": str(e)}


@router.post("/forms/generate")
async def generate_form(req: GenerateFormsRequest):
    """Generate a Google Forms quiz using Gemini + Forms API."""
    from src.lms_agents.tools.google_forms import generate_form_questions, create_quiz_form

    try:
        # 1. Generate questions via Gemini
        questions = generate_form_questions(
            topic=req.topic,
            standards=[],
            grade=req.grade,
            question_count=req.question_count,
            question_types=req.question_types,
        )

        if not questions:
            return {"error": "Failed to generate quiz questions"}

        # 2. Create Google Form with quiz settings
        result = create_quiz_form(
            teacher_id=req.teacher_id,
            title=f"{req.topic} — Grade {req.grade} {req.subject} Quiz",
            questions=questions,
        )

        if not result:
            return {"error": "Failed to create Google Form. Is your Google account connected?"}

        return {
            "form_id": result.get("form_id", ""),
            "form_url": result.get("form_url", ""),
            "responder_url": result.get("responder_url", ""),
            "question_count": result.get("question_count", len(questions)),
            "status": "complete",
        }

    except Exception as e:
        log.error(f"[Forms] Generation failed: {e}")
        return {"error": str(e)}
