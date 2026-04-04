"""Chat sidebar routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/message")
async def chat_message():
    """Chat sidebar message."""
    return {"status": "stub"}
