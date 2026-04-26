"""
Teacher auth — register, login, current-user.

Phase 28: real auth replaces the stub. Email + password creates a teacher
row with a bcrypt password_hash; login returns a JWT the dashboard stores
as the Authorization Bearer token. `/me` round-trips the token to the
teacher record so the dashboard can hydrate the current user on app boot.

Google OAuth endpoints kept as stubs — Google sign-in flows through the
existing OAuth handlers in `routers/google_oauth.py` (per CLAUDE.md decision
6/19/21). They will eventually issue the same JWT.
"""
import os
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, EmailStr, Field

from src.lms_agents.tools.auth import (
    decode_token, hash_password, make_token, require_teacher, verify_password,
)
from src.lms_agents.tools.db import get_connection

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    teacher_id: str
    email: str
    name: str


class MeResponse(BaseModel):
    teacher_id: str
    email: str
    name: str
    tier: str | None = None
    onboarding_complete: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """
    Email/password registration. Returns a JWT the client stores as
    Authorization Bearer for subsequent API calls.
    """
    email = req.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email")

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT teacher_id FROM teachers WHERE email = %s", (email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Email already registered")

        teacher_id = str(uuid4())
        cur.execute(
            """INSERT INTO teachers
                 (teacher_id, email, name, password_hash, auth_provider,
                  credits_purchased, clip_previews_used_this_month)
               VALUES (%s::uuid, %s, %s, %s, 'email', 0, 0)""",
            (teacher_id, email, req.name.strip(), hash_password(req.password)),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    token = make_token(teacher_id, email)
    return TokenResponse(
        access_token=token, teacher_id=teacher_id,
        email=email, name=req.name.strip(),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Verify email/password, return a JWT."""
    email = req.email.strip().lower()
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """SELECT teacher_id, email, name, password_hash
               FROM teachers WHERE email = %s""",
            (email,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if not row or not row.get("password_hash") or not verify_password(req.password, row["password_hash"]):
        # Same response shape for "no such user" and "wrong password" so
        # callers can't enumerate accounts.
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = make_token(str(row["teacher_id"]), row["email"])
    return TokenResponse(
        access_token=token, teacher_id=str(row["teacher_id"]),
        email=row["email"], name=row["name"],
    )


@router.get("/me", response_model=MeResponse)
async def me(teacher_id: str = Depends(require_teacher)):
    """Return the current authenticated teacher's profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """SELECT teacher_id, email, name, tier, onboarding_complete
               FROM teachers WHERE teacher_id = %s::uuid""",
            (teacher_id,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return MeResponse(
        teacher_id=str(row["teacher_id"]),
        email=row["email"],
        name=row["name"],
        tier=row.get("tier"),
        onboarding_complete=row.get("onboarding_complete"),
    )


# Google OAuth stubs preserved — real flow lives in routers/google_oauth.py.
@router.get("/google")
async def google_auth():
    return {"status": "stub — see routers/google_oauth.py for the real flow"}


@router.get("/google/callback")
async def google_callback(code: str = "", state: str = ""):
    return {"status": "stub — see routers/google_oauth.py for the real flow"}
