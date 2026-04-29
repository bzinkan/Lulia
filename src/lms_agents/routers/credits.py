"""Credit system routes — status, history, pre-check."""
from fastapi import APIRouter, Depends

from src.lms_agents.tools.auth import require_teacher

router = APIRouter(prefix="/credits", tags=["Credits"])


@router.get("/status")
async def credit_status(_teacher_id: str = Depends(require_teacher)):
    """Credits remaining, tier info."""
    return {"credits_remaining": 50, "tier": "basic", "status": "stub"}


@router.get("/history")
async def credit_history(_teacher_id: str = Depends(require_teacher)):
    """Transaction history."""
    return {"transactions": [], "status": "stub"}


@router.post("/check")
async def credit_check(_teacher_id: str = Depends(require_teacher)):
    """Pre-check before generation."""
    return {"sufficient": True, "status": "stub"}
