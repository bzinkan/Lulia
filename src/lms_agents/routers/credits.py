"""Credit system routes — status, history, pre-check."""
from fastapi import APIRouter

router = APIRouter(prefix="/credits", tags=["Credits"])


@router.get("/status")
async def credit_status():
    """Credits remaining, tier info."""
    return {"credits_remaining": 50, "tier": "basic", "status": "stub"}


@router.get("/history")
async def credit_history():
    """Transaction history."""
    return {"transactions": [], "status": "stub"}


@router.post("/check")
async def credit_check():
    """Pre-check before generation."""
    return {"sufficient": True, "status": "stub"}
