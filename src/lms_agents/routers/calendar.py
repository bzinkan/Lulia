"""Calendar routes — Google sync, Classroom sync, PDF."""
from fastapi import APIRouter

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.post("/sync-google")
async def sync_google_calendar():
    """Sync to Google Calendar."""
    return {"status": "stub"}


@router.post("/sync-classroom")
async def sync_classroom():
    """Organize Classroom topics."""
    return {"status": "stub"}


@router.get("/pdf")
async def calendar_pdf():
    """Generate visual calendar PDF."""
    return {"status": "stub"}
