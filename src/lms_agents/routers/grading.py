"""Grading routes — scan upload, pending reviews."""
from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="", tags=["Grading"])


@router.post("/scans/upload")
async def upload_scan(file: UploadFile = File(...)):
    """Manual scan upload."""
    return {"filename": file.filename, "status": "stub"}


@router.get("/reviews/pending")
async def pending_reviews():
    """Unified: paper + interactive."""
    return {"reviews": [], "status": "stub"}
