"""Google Classroom routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/classroom", tags=["Classroom"])


@router.post("/connect")
async def connect_classroom():
    """Connect Google Classroom."""
    return {"status": "stub"}


@router.get("/callback")
async def classroom_callback(code: str = "", state: str = ""):
    """OAuth callback for Classroom."""
    return {"status": "stub"}
