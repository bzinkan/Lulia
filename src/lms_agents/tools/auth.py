"""
Teacher auth — bcrypt password hashing + JWT session tokens.

Public:
  hash_password(plaintext) -> str           # for /auth/register
  verify_password(plaintext, hashed) -> bool# for /auth/login
  make_token(teacher_id, email) -> str      # JWT for the client
  decode_token(token) -> dict | None        # for require_teacher
  require_teacher                           # FastAPI dependency
                                              -> teacher_id (str)

Dev bypass:
  Set DEV_AUTH_BYPASS=1 (the default in dev) to allow legacy
  `?teacher_id=<uuid>` query/form/json fallback when no Authorization
  header is present. Production MUST set DEV_AUTH_BYPASS=0.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JWT_ALG = "HS256"
JWT_EXP_HOURS = int(os.environ.get("JWT_EXP_HOURS", "168"))  # 7 days


def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret
    # Dev fallback — DERIVE from DB password so it's stable per dev box.
    # NEVER ship without JWT_SECRET set in prod (verified in main.py).
    fallback = os.environ.get("DB_PASSWORD", "devpassword") + "_lulia_jwt_dev"
    return fallback


def _dev_bypass_enabled() -> bool:
    return os.environ.get("DEV_AUTH_BYPASS", "1") == "1"


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plaintext: str) -> str:
    return _pwd_context.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    if not plaintext or not hashed:
        return False
    try:
        return _pwd_context.verify(plaintext, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def make_token(teacher_id: str, email: str) -> str:
    """Issue a session JWT. Returns the encoded string."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(teacher_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_EXP_HOURS)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[dict]:
    """Verify + decode. Returns claims dict or None on any error."""
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALG])
    except JWTError as e:
        log.debug(f"[Auth] JWT decode failed: {e}")
        return None


# ---------------------------------------------------------------------------
# require_teacher — the FastAPI dependency every protected route uses
# ---------------------------------------------------------------------------

# `auto_error=False` lets us fall through to the dev-bypass path before 401-ing.
_bearer = HTTPBearer(auto_error=False)


async def require_teacher(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """
    Resolve the authenticated teacher_id for this request.

    Order of resolution:
      1. `Authorization: Bearer <jwt>` header (production path).
      2. DEV_AUTH_BYPASS=1: legacy `teacher_id` from query string / form /
         json body. Keeps existing dashboard + scripts working while we
         migrate every route to real auth.
      3. Otherwise → 401.

    Returns the teacher_id (str). Routers that need extra claims should
    call `decode_token(creds.credentials)` themselves.
    """
    # Path 1: Bearer token
    if creds and creds.credentials:
        claims = decode_token(creds.credentials)
        if claims and claims.get("sub"):
            return str(claims["sub"])
        # Header was present but invalid — fail loudly even in dev.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Path 2: dev bypass (legacy teacher_id param)
    if _dev_bypass_enabled():
        # Query string
        qs_tid = request.query_params.get("teacher_id")
        if qs_tid:
            return qs_tid
        # Form body — only if already buffered (avoid re-reading streams)
        try:
            ct = (request.headers.get("content-type") or "").lower()
            if "application/x-www-form-urlencoded" in ct or "multipart/form-data" in ct:
                form = await request.form()
                form_tid = form.get("teacher_id")
                if form_tid:
                    return str(form_tid)
        except Exception:
            pass
        # JSON body — peek without consuming the request stream
        try:
            ct = (request.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                body_bytes = await request.body()
                if body_bytes:
                    import json as _json
                    body = _json.loads(body_bytes)
                    if isinstance(body, dict):
                        body_tid = body.get("teacher_id")
                        if body_tid:
                            # Stash so downstream `await request.json()` works
                            # by re-parsing from the cached body.
                            return str(body_tid)
        except Exception:
            pass
        # Last-ditch dev fallback: the seed teacher.
        return "00000000-0000-0000-0000-000000000001"

    # Path 3: hard fail
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def assert_owner_or_403(authenticated_teacher_id: str, resource_teacher_id: str) -> None:
    """Raise 403 if the authenticated teacher doesn't own the resource.
    Use after `require_teacher` for every CRUD on a tenant-scoped resource.
    """
    if str(authenticated_teacher_id) != str(resource_teacher_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource",
        )
