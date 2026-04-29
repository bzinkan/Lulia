"""Settings routes."""
from fastapi import APIRouter, Depends

from src.lms_agents.tools.auth import require_teacher

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
async def get_settings(_teacher_id: str = Depends(require_teacher)):
    """Get teacher settings."""
    return {"settings": {}, "status": "stub"}


@router.put("")
async def update_settings(_teacher_id: str = Depends(require_teacher)):
    """Update teacher settings."""
    return {"status": "stub"}
