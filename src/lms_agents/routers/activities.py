"""Interactive activity routes — generate, detail, launch, responses."""
from uuid import UUID
from fastapi import APIRouter

router = APIRouter(prefix="/activities", tags=["Interactive"])


@router.post("/generate")
async def generate_activity():
    """Generate React interactive."""
    return {"status": "stub"}


@router.get("/{activity_id}")
async def get_activity(activity_id: UUID):
    """Activity detail + student link."""
    return {"activity_id": str(activity_id), "status": "stub"}


@router.post("/{activity_id}/launch")
async def launch_game(activity_id: UUID):
    """Launch live game -> returns game PIN."""
    return {"activity_id": str(activity_id), "game_pin": "stub", "status": "stub"}


@router.post("/responses/{response_id}")
async def submit_response(response_id: UUID):
    """Student submits responses."""
    return {"response_id": str(response_id), "status": "stub"}
