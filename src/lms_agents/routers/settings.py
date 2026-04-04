"""Settings routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
async def get_settings():
    """Get teacher settings."""
    return {"settings": {}, "status": "stub"}


@router.put("")
async def update_settings():
    """Update teacher settings."""
    return {"status": "stub"}
