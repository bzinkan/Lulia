"""Student access routes — Google SSO, class code, unique link."""
from fastapi import APIRouter

router = APIRouter(prefix="/student", tags=["Student Access"])


@router.post("/auth/google")
async def student_google_auth():
    """Google SSO for students."""
    return {"status": "stub"}


@router.post("/auth/class-code")
async def student_class_code():
    """Class code + name + PIN."""
    return {"status": "stub"}


@router.get("/activity/{token}")
async def student_activity_link(token: str):
    """Unique link access."""
    return {"token": token, "status": "stub"}
