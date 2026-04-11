"""Class Intelligence API — per-class context accumulation endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.lms_agents.tools.class_intelligence import (
    get_class_context,
    get_ai_context_prompt,
    record_standard_covered,
    rate_activity as _rate_activity,
    note_misconception as _note_misconception,
    add_vocabulary as _add_vocabulary,
    update_class_profile as _update_class_profile,
    update_pacing as _update_pacing,
    rebuild_ai_context,
    get_current_curriculum_context,
    get_standards_coverage,
    override_position,
)
from src.lms_agents.tools.curriculum_generator import generate_curriculum_from_standards

log = logging.getLogger(__name__)

router = APIRouter(prefix="/classes/{class_id}/intelligence", tags=["Class Intelligence"])


# --- Request models ---

class StandardCoveredRequest(BaseModel):
    code: str


class RateActivityRequest(BaseModel):
    activity_id: str
    type: str
    topic: str
    rating: int
    notes: str = ""


class MisconceptionRequest(BaseModel):
    topic: str
    misconception: str
    correction: str = ""


class VocabularyTerm(BaseModel):
    term: str
    definition: str = ""
    subject_area: str = ""


class VocabularyRequest(BaseModel):
    terms: list[VocabularyTerm]


class ProfileRequest(BaseModel):
    strengths: Optional[list[str]] = None
    challenges: Optional[list[str]] = None


class PacingRequest(BaseModel):
    status: str
    current_unit: str = ""
    notes: str = ""


# --- Endpoints ---

@router.get("/")
async def get_intelligence(class_id: str):
    """Get full class intelligence for a class."""
    try:
        ctx = get_class_context(class_id)
        return ctx
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to get intelligence: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/context")
async def get_context_prompt(class_id: str):
    """Get just the AI context prompt string."""
    try:
        prompt = get_ai_context_prompt(class_id)
        return {"class_id": class_id, "context_prompt": prompt}
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to get context: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/standard-covered")
async def standard_covered(class_id: str, req: StandardCoveredRequest):
    """Record a standard as covered."""
    try:
        record_standard_covered(class_id, req.code)
        return {"status": "ok", "standard": req.code}
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to record standard: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/rate-activity")
async def rate_activity_endpoint(class_id: str, req: RateActivityRequest):
    """Rate an activity's effectiveness."""
    try:
        _rate_activity(class_id, req.activity_id, req.type, req.topic, req.rating, req.notes)
        return {"status": "ok"}
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to rate activity: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/misconception")
async def misconception_endpoint(class_id: str, req: MisconceptionRequest):
    """Note a common misconception."""
    try:
        _note_misconception(class_id, req.topic, req.misconception, req.correction)
        return {"status": "ok"}
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to note misconception: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/vocabulary")
async def vocabulary_endpoint(class_id: str, req: VocabularyRequest):
    """Add vocabulary terms."""
    try:
        terms = [t.model_dump() for t in req.terms]
        _add_vocabulary(class_id, terms)
        return {"status": "ok", "count": len(terms)}
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to add vocabulary: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/profile")
async def profile_endpoint(class_id: str, req: ProfileRequest):
    """Update class strengths and/or challenges."""
    try:
        _update_class_profile(class_id, strengths=req.strengths, challenges=req.challenges)
        return {"status": "ok"}
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to update profile: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/pacing")
async def pacing_endpoint(class_id: str, req: PacingRequest):
    """Update pacing status."""
    try:
        _update_pacing(class_id, req.status, req.current_unit, req.notes)
        return {"status": "ok"}
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to update pacing: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/rebuild")
async def rebuild_endpoint(class_id: str):
    """Force rebuild of AI context summary."""
    try:
        summary = rebuild_ai_context(class_id)
        return {"status": "ok", "context_prompt": summary}
    except Exception as e:
        log.error(f"[ClassIntel API] Failed to rebuild context: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Curriculum position + generation endpoints
# ---------------------------------------------------------------------------

@router.get("/curriculum/position")
async def curriculum_position_endpoint(class_id: str):
    """Get the teacher's current curriculum position for this class."""
    try:
        ctx = get_current_curriculum_context(class_id)
        if ctx is None:
            return {"has_curriculum": False}
        return {"has_curriculum": True, **ctx}
    except Exception as e:
        log.error(f"[ClassIntel API] Curriculum position failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/curriculum/gaps")
async def curriculum_gaps_endpoint(class_id: str):
    """
    Get standards coverage for a class — works WITH or WITHOUT a curriculum.
    Without: flat list of covered standards from activity log.
    With: grouped by unit with per-unit completion percentages.
    """
    try:
        return get_standards_coverage(class_id)
    except Exception as e:
        log.error(f"[ClassIntel API] Curriculum gaps failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


class PositionOverrideRequest(BaseModel):
    target_calendar_id: str


@router.post("/curriculum/jump")
async def curriculum_jump_endpoint(class_id: str, req: PositionOverrideRequest):
    """Teacher manually jumps to a specific unit."""
    try:
        override_position(class_id, req.target_calendar_id)
        ctx = get_current_curriculum_context(class_id)
        return {"status": "ok", "new_position": ctx}
    except Exception as e:
        log.error(f"[ClassIntel API] Position jump failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


class GenerateCurriculumRequest(BaseModel):
    grade_level: str
    subject: str
    state_code: str
    scope: str = "full_year"  # "full_year" or "next_unit"


@router.post("/curriculum/generate")
async def generate_curriculum_endpoint(class_id: str, req: GenerateCurriculumRequest):
    """
    Generate a curriculum from state standards for this class.

    The teacher picks grade + subject + state, and the system builds a
    scope & sequence using the standards already loaded in the database.
    """
    try:
        result = generate_curriculum_from_standards(
            grade_level=req.grade_level,
            subject=req.subject,
            state_code=req.state_code,
            scope=req.scope,
            class_id=class_id,
        )
        if result.get("error"):
            return JSONResponse({"error": result["error"]}, status_code=400)
        return result
    except Exception as e:
        log.error(f"[ClassIntel API] Curriculum generation failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
