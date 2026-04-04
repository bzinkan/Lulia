"""Accommodation routes — profiles and modified generation."""
from fastapi import APIRouter

router = APIRouter(prefix="/accommodations", tags=["Accommodations"])


@router.get("/profiles")
async def list_profiles():
    """List teacher's accommodation profiles."""
    return {"profiles": [], "status": "stub"}


@router.post("/profiles")
async def create_profile():
    """Create IEP/504/ELL/Gifted profile."""
    return {"status": "stub"}


@router.post("/generate")
async def generate_accommodated():
    """Generate modified version of assignment."""
    return {"status": "stub"}
