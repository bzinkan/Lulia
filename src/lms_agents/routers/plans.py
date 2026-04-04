"""Plan routes — suggest, approve, preview, start-over."""
from uuid import UUID
from fastapi import APIRouter

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.post("/suggest")
async def suggest_plan(duration: str = "week"):
    """Trigger Planner (accepts duration: day/week/unit/semester/year)."""
    return {"status": "stub", "duration": duration}


@router.get("/{plan_id}/preview")
async def preview_plan(plan_id: UUID):
    """Rich visual preview thumbnails."""
    return {"plan_id": str(plan_id), "status": "stub"}


@router.put("/{plan_id}/approve")
async def approve_plan(plan_id: UUID):
    """Approve plan and trigger generation."""
    return {"plan_id": str(plan_id), "status": "approved"}


@router.put("/{plan_id}/start-over")
async def start_over(plan_id: UUID):
    """Discard and regenerate fresh."""
    return {"plan_id": str(plan_id), "status": "discarded"}
