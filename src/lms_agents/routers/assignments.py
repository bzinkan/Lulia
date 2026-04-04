"""Assignment routes — generate and retrieve."""
from uuid import UUID
from fastapi import APIRouter

router = APIRouter(prefix="/assignments", tags=["Assignments"])


@router.post("/generate")
async def generate_assignment():
    """Path 2: quick one-off generation."""
    return {"status": "stub"}


@router.get("/{assignment_id}")
async def get_assignment(assignment_id: UUID):
    """Assignment detail."""
    return {"assignment_id": str(assignment_id), "status": "stub"}
