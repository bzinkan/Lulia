"""Analytics routes."""
from uuid import UUID
from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/class/{class_id}")
async def class_analytics(class_id: UUID):
    """Class analytics."""
    return {"class_id": str(class_id), "status": "stub"}
