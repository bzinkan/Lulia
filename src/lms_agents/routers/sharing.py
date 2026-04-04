"""Sharing routes — generate link, view, remix."""
from uuid import UUID
from fastapi import APIRouter

router = APIRouter(prefix="/share", tags=["Sharing"])


@router.post("/{assignment_id}")
async def create_share_link(assignment_id: UUID):
    """Generate share link."""
    return {"assignment_id": str(assignment_id), "status": "stub"}


@router.get("/{token}")
async def view_shared(token: str):
    """View shared resource."""
    return {"token": token, "status": "stub"}


@router.post("/{token}/remix")
async def remix_shared(token: str):
    """Copy + modify for my class."""
    return {"token": token, "status": "stub"}
