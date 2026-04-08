"""
Canva OAuth 2.0 with PKCE — token storage, refresh, and authenticated API calls.

Tokens are encrypted with AES-256 (Fernet) before storing in the teachers table.
"""
import hashlib
import json
import logging
import os
import secrets
import time
from base64 import b64encode, urlsafe_b64encode

from cryptography.fernet import Fernet

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
CANVA_API_BASE = "https://api.canva.com/rest/v1"


# ---------------------------------------------------------------------------
# Encryption helpers (mirrors google_auth.py pattern)
# ---------------------------------------------------------------------------

def _get_encryption_key() -> bytes:
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if key:
        return key.encode()
    secret = os.environ.get("CANVA_CLIENT_SECRET", "default-dev-secret")
    return b64encode(hashlib.sha256(secret.encode()).digest())


def _encrypt(data: str) -> str:
    f = Fernet(_get_encryption_key())
    return f.encrypt(data.encode()).decode()


def _decrypt(data: str) -> str:
    f = Fernet(_get_encryption_key())
    return f.decrypt(data.encode()).decode()


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = secrets.token_urlsafe(64)[:128]  # 43-128 chars
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def store_code_verifier(teacher_id: str, code_verifier: str):
    """Persist the PKCE code_verifier so the callback can use it."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teachers SET canva_code_verifier = %s WHERE teacher_id = %s",
        (code_verifier, teacher_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_code_verifier(teacher_id: str) -> str | None:
    """Retrieve the stored code_verifier for a teacher."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT canva_code_verifier FROM teachers WHERE teacher_id = %s",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Token storage
# ---------------------------------------------------------------------------

def store_canva_credentials(
    teacher_id: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
):
    """Encrypt and store Canva OAuth tokens for a teacher."""
    creds = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": int(time.time()) + expires_in,
    }
    encrypted = _encrypt(json.dumps(creds))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE teachers
           SET canva_access_token = %s,
               canva_refresh_token = %s,
               canva_token_expires_at = to_timestamp(%s),
               canva_code_verifier = NULL
           WHERE teacher_id = %s""",
        (encrypted, encrypted, creds["expires_at"], teacher_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    log.info(f"[Canva Auth] Stored credentials for teacher {teacher_id}")


def get_canva_credentials(teacher_id: str) -> dict | None:
    """Load, decrypt, and (if needed) refresh Canva tokens for a teacher."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT canva_access_token FROM teachers WHERE teacher_id = %s",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row[0]:
        return None

    try:
        creds = json.loads(_decrypt(row[0]))
    except Exception as e:
        log.warning(f"Failed to decrypt Canva credentials: {e}")
        return None

    # Auto-refresh if expired (with 60s buffer)
    if creds.get("expires_at", 0) < time.time() + 60:
        refreshed = refresh_canva_token(teacher_id, creds["refresh_token"])
        if refreshed:
            return refreshed
        return None

    return creds


def refresh_canva_token(teacher_id: str, refresh_token: str) -> dict | None:
    """Use the refresh_token to get a new access_token from Canva."""
    import httpx

    client_id = os.environ.get("CANVA_CLIENT_ID", "")
    client_secret = os.environ.get("CANVA_CLIENT_SECRET", "")

    try:
        resp = httpx.post(
            CANVA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", refresh_token)
        expires_in = data.get("expires_in", 3600)

        store_canva_credentials(teacher_id, new_access, new_refresh, expires_in)
        log.info(f"[Canva Auth] Refreshed token for teacher {teacher_id}")
        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_at": int(time.time()) + expires_in,
        }
    except Exception as e:
        log.error(f"[Canva Auth] Token refresh failed: {e}")
        return None


def remove_canva_credentials(teacher_id: str):
    """Clear all Canva tokens for a teacher."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE teachers
           SET canva_access_token = NULL,
               canva_refresh_token = NULL,
               canva_token_expires_at = NULL,
               canva_code_verifier = NULL
           WHERE teacher_id = %s""",
        (teacher_id,),
    )
    conn.commit()
    cur.close()
    conn.close()
    log.info(f"[Canva Auth] Removed credentials for teacher {teacher_id}")


def is_connected(teacher_id: str) -> bool:
    """Check if a teacher has Canva tokens stored."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT canva_access_token FROM teachers WHERE teacher_id = %s",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row and row[0])


# ---------------------------------------------------------------------------
# Authenticated API call helper
# ---------------------------------------------------------------------------

def canva_api_call(
    teacher_id: str,
    method: str,
    endpoint: str,
    **kwargs,
) -> dict:
    """Make an authenticated request to the Canva Connect API.

    Args:
        teacher_id: teacher whose tokens to use
        method: HTTP method (GET, POST, etc.)
        endpoint: path relative to CANVA_API_BASE, e.g. "/designs"
        **kwargs: passed to httpx.request (json, params, etc.)

    Returns:
        Parsed JSON response.

    Raises:
        ValueError if teacher is not connected.
        httpx.HTTPStatusError on API errors.
    """
    import httpx

    creds = get_canva_credentials(teacher_id)
    if not creds:
        raise ValueError("Teacher is not connected to Canva")

    url = f"{CANVA_API_BASE}{endpoint}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {creds['access_token']}"

    resp = httpx.request(method, url, headers=headers, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()
