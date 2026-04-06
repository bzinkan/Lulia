"""
Google OAuth 2.0 — handles auth flow, token storage, refresh, and revocation.

Tokens are encrypted with AES-256 before storing in teachers.google_credentials_encrypted.
"""
import json
import logging
import os
from base64 import b64decode, b64encode

from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/classroom.coursework.students",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/forms.body",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def _get_encryption_key() -> bytes:
    """Get or derive the Fernet encryption key from env."""
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if key:
        return key.encode()
    # Derive from a secret — in production use a proper key
    secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "default-dev-secret")
    import hashlib
    return b64encode(hashlib.sha256(secret.encode()).digest())


def _encrypt(data: str) -> str:
    """Encrypt a string with Fernet."""
    f = Fernet(_get_encryption_key())
    return f.encrypt(data.encode()).decode()


def _decrypt(data: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    f = Fernet(_get_encryption_key())
    return f.decrypt(data.encode()).decode()


def get_oauth_flow(redirect_uri: str | None = None) -> Flow:
    """Create an OAuth 2.0 flow for Google sign-in."""
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    redirect = redirect_uri or os.environ.get(
        "GOOGLE_OAUTH_REDIRECT", "http://localhost:8000/api/v1/classroom/auth/callback"
    )

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect],
        }
    }

    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = redirect
    return flow


def get_auth_url(teacher_id: str) -> str:
    """Generate the OAuth consent URL. State carries teacher_id."""
    flow = get_oauth_flow()
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=teacher_id,
    )
    return url


def handle_callback(code: str, teacher_id: str) -> dict:
    """Exchange auth code for tokens, encrypt and store."""
    flow = get_oauth_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Serialize credentials
    creds_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
    }

    # Encrypt and store
    encrypted = _encrypt(json.dumps(creds_data))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE teachers
           SET google_credentials_encrypted = %s, auth_provider = 'google'
           WHERE teacher_id = %s""",
        (encrypted, teacher_id),
    )
    conn.commit()
    cur.close()
    conn.close()

    log.info(f"[Google Auth] Stored credentials for teacher {teacher_id}")
    return {"status": "connected", "email": "connected"}


def get_credentials(teacher_id: str) -> Credentials | None:
    """Load and decrypt stored credentials for a teacher. Refreshes if expired."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT google_credentials_encrypted FROM teachers WHERE teacher_id = %s",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row[0]:
        return None

    try:
        creds_data = json.loads(_decrypt(row[0]))
    except Exception as e:
        log.warning(f"Failed to decrypt credentials: {e}")
        return None

    credentials = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=creds_data.get("scopes"),
    )

    # Refresh if expired
    if credentials.expired and credentials.refresh_token:
        from google.auth.transport.requests import Request
        credentials.refresh(Request())
        # Re-store refreshed token
        creds_data["token"] = credentials.token
        encrypted = _encrypt(json.dumps(creds_data))
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE teachers SET google_credentials_encrypted = %s WHERE teacher_id = %s",
            (encrypted, teacher_id),
        )
        conn.commit()
        cur.close()
        conn.close()

    return credentials


def revoke_credentials(teacher_id: str) -> bool:
    """Revoke Google tokens and remove from DB."""
    credentials = get_credentials(teacher_id)
    if credentials and credentials.token:
        import httpx
        httpx.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": credentials.token},
        )

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teachers SET google_credentials_encrypted = NULL WHERE teacher_id = %s",
        (teacher_id,),
    )
    conn.commit()
    cur.close()
    conn.close()
    return True


def is_connected(teacher_id: str) -> bool:
    """Check if a teacher has Google credentials stored."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT google_credentials_encrypted FROM teachers WHERE teacher_id = %s",
        (teacher_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row and row[0])
