"""Teacher auth routes — Google OAuth, email/password."""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register")
async def register():
    """Email/password registration."""
    return {"status": "stub"}


@router.post("/login")
async def login():
    """Email/password login."""
    return {"status": "stub"}


@router.get("/google")
async def google_auth():
    """Initiate Google OAuth."""
    return {"status": "stub"}


@router.get("/google/callback")
async def google_callback(code: str = "", state: str = ""):
    """Google OAuth callback."""
    return {"status": "stub"}
