"""Canva Connect API — OAuth with PKCE, design creation, export."""
import logging
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from src.lms_agents.tools.canva_auth import (
    generate_pkce,
    store_code_verifier,
    get_code_verifier,
    store_canva_credentials,
    get_canva_credentials,
    remove_canva_credentials,
    is_connected,
    canva_api_call,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/canva", tags=["Canva"])

CANVA_AUTH_URL = "https://www.canva.com/api/oauth/authorize"
CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
CANVA_SCOPES = "design:content:write design:content:read design:meta:read"


def _callback_uri() -> str:
    return os.environ.get(
        "CANVA_REDIRECT_URI",
        "http://localhost:8000/api/v1/canva/auth/callback",
    )


def _client_id() -> str:
    return os.environ.get("CANVA_CLIENT_ID", "")


def _client_secret() -> str:
    return os.environ.get("CANVA_CLIENT_SECRET", "")


# ── OAuth ─────────────────────────────────────────────────────────────────

@router.get("/auth/start")
async def start_auth(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
):
    """Redirect the teacher to Canva's OAuth consent screen (PKCE)."""
    verifier, challenge = generate_pkce()
    store_code_verifier(teacher_id, verifier)

    params = urlencode({
        "response_type": "code",
        "client_id": _client_id(),
        "redirect_uri": _callback_uri(),
        "scope": CANVA_SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": teacher_id,
    })
    return RedirectResponse(f"{CANVA_AUTH_URL}?{params}")


@router.get("/auth/callback")
async def auth_callback(code: str = "", state: str = ""):
    """Handle the OAuth redirect from Canva."""
    if not code:
        return JSONResponse({"error": "No authorization code"}, status_code=400)

    teacher_id = state
    verifier = get_code_verifier(teacher_id)
    if not verifier:
        return JSONResponse({"error": "Missing PKCE verifier — restart the flow"}, status_code=400)

    import httpx

    try:
        resp = httpx.post(
            CANVA_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _callback_uri(),
                "code_verifier": verifier,
                "client_id": _client_id(),
                "client_secret": _client_secret(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        log.error(f"[Canva OAuth] Token exchange failed: {e.response.text}")
        return JSONResponse({"error": "Token exchange failed"}, status_code=502)
    except Exception as e:
        log.error(f"[Canva OAuth] Token exchange error: {e}")
        return JSONResponse({"error": str(e)}, status_code=502)

    store_canva_credentials(
        teacher_id,
        data["access_token"],
        data.get("refresh_token", ""),
        data.get("expires_in", 3600),
    )

    return RedirectResponse("http://localhost:3001/settings?canva=connected")


@router.get("/status")
async def check_status(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
):
    """Check whether a teacher has a connected Canva account."""
    connected = is_connected(teacher_id)
    return {"connected": connected, "teacher_id": teacher_id}


@router.post("/disconnect")
async def disconnect(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
):
    """Remove stored Canva tokens for a teacher."""
    remove_canva_credentials(teacher_id)
    return {"status": "disconnected"}


# ── Design endpoints ─────────────────────────────────────────────────────

DESIGN_TYPE_MAP = {
    "document": {"design_type": "doc", "width": 816, "height": 1056},
    "presentation": {"design_type": "presentation", "width": 1920, "height": 1080},
    "poster": {"design_type": "poster", "width": 1080, "height": 1080},
}


class CreateDesignRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    title: str = "Untitled Design"
    design_type: str = "document"  # document | presentation | poster


@router.post("/design/create")
async def create_design(req: CreateDesignRequest):
    """Create a new blank design in the teacher's Canva account.

    Returns the design_id and edit_url so the teacher can open it directly.
    """
    type_cfg = DESIGN_TYPE_MAP.get(req.design_type, DESIGN_TYPE_MAP["document"])

    try:
        result = canva_api_call(
            req.teacher_id,
            "POST",
            "/designs",
            json={
                "design_type": {
                    "type": type_cfg["design_type"],
                },
                "title": req.title,
            },
        )
        design = result.get("design", result)
        return {
            "design_id": design.get("id"),
            "title": design.get("title"),
            "edit_url": design.get("urls", {}).get("edit_url"),
            "view_url": design.get("urls", {}).get("view_url"),
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        log.error(f"[Canva] Create design failed: {e}")
        return JSONResponse({"error": f"Failed to create design: {e}"}, status_code=502)


@router.get("/design/{design_id}")
async def get_design(
    design_id: str,
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
):
    """Fetch details of an existing Canva design."""
    try:
        result = canva_api_call(teacher_id, "GET", f"/designs/{design_id}")
        design = result.get("design", result)
        return {
            "design_id": design.get("id"),
            "title": design.get("title"),
            "edit_url": design.get("urls", {}).get("edit_url"),
            "view_url": design.get("urls", {}).get("view_url"),
            "thumbnail": design.get("thumbnail"),
            "created_at": design.get("created_at"),
            "updated_at": design.get("updated_at"),
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        log.error(f"[Canva] Get design failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=502)


class ExportDesignRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    design_id: str
    format: str = "pdf"  # pdf | png | jpg


@router.post("/design/export")
async def export_design(req: ExportDesignRequest):
    """Request an export of a Canva design to PDF/PNG/JPG.

    Canva exports are async — this returns an export job ID. Poll
    GET /canva/design/export/{export_id} until status is 'completed'.
    """
    try:
        result = canva_api_call(
            req.teacher_id,
            "POST",
            "/exports",
            json={
                "design_id": req.design_id,
                "format": {
                    "type": req.format,
                },
            },
        )
        job = result.get("job", result)
        return {
            "export_id": job.get("id"),
            "status": job.get("status"),
            "design_id": req.design_id,
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        log.error(f"[Canva] Export failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=502)


@router.get("/design/export/{export_id}")
async def get_export_status(
    export_id: str,
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
):
    """Poll the status of a Canva export job.

    When status is 'completed', the response includes a download URL.
    """
    try:
        result = canva_api_call(teacher_id, "GET", f"/exports/{export_id}")
        job = result.get("job", result)
        return {
            "export_id": job.get("id"),
            "status": job.get("status"),
            "urls": job.get("urls"),
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        log.error(f"[Canva] Export status check failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=502)
