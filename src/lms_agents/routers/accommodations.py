"""Accommodation routes — profiles CRUD + generate modified versions."""
import os
from uuid import UUID, uuid4
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.accommodation_engine import (
    get_all_profiles, get_profile, apply_modifications, DEFAULT_PROFILES,
)
from src.lms_agents.tools.template_renderer import render_template

router = APIRouter(prefix="/accommodations", tags=["Accommodations"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


class CreateProfileRequest(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    name: str
    type: str  # iep, 504, ell, gifted, custom
    modifications: dict


class GenerateRequest(BaseModel):
    assignment_id: str
    profiles: list[str]  # profile IDs
    teacher_id: str = "00000000-0000-0000-0000-000000000001"


@router.get("/profiles")
async def list_profiles(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
):
    """List all accommodation profiles (defaults + custom)."""
    profiles = get_all_profiles(teacher_id)
    return {"profiles": profiles}


@router.post("/profiles")
async def create_profile(req: CreateProfileRequest, conn=Depends(get_db)):
    """Create a custom accommodation profile."""
    cur = conn.cursor()
    profile_id = str(uuid4())
    cur.execute(
        """INSERT INTO accommodation_profiles
           (profile_id, teacher_id, name, type, modifications, is_default)
           VALUES (%s, %s::uuid, %s, %s, %s, false)""",
        (profile_id, req.teacher_id, req.name, req.type, Json(req.modifications)),
    )
    conn.commit()
    cur.close()
    return {"profile_id": profile_id, "status": "created"}


@router.put("/profiles/{profile_id}")
async def update_profile(profile_id: UUID, req: CreateProfileRequest, conn=Depends(get_db)):
    """Update a custom profile."""
    cur = conn.cursor()
    cur.execute(
        """UPDATE accommodation_profiles
           SET name = %s, type = %s, modifications = %s
           WHERE profile_id = %s""",
        (req.name, req.type, Json(req.modifications), str(profile_id)),
    )
    if cur.rowcount == 0:
        cur.close()
        return JSONResponse({"error": "Profile not found"}, status_code=404)
    conn.commit()
    cur.close()
    return {"profile_id": str(profile_id), "status": "updated"}


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: UUID, conn=Depends(get_db)):
    """Delete a custom profile."""
    cur = conn.cursor()
    cur.execute("DELETE FROM accommodation_profiles WHERE profile_id = %s", (str(profile_id),))
    conn.commit()
    cur.close()
    return {"status": "deleted"}


@router.post("/generate")
async def generate_accommodated(req: GenerateRequest, conn=Depends(get_db)):
    """
    Generate modified versions of an existing assignment for each profile.

    Uses the SAME template and theme (dignity principle).
    Returns array of new assignment IDs.
    """
    # Get the original assignment
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM assignments WHERE assignment_id = %s",
        (req.assignment_id,),
    )
    original = cur.fetchone()
    cur.close()

    if not original:
        return JSONResponse({"error": "Assignment not found"}, status_code=404)

    original_content = original["questions"] or []
    template_id = original["output_template_id"]
    design_theme = original.get("design_theme", "modern_clean")
    subject = ""  # Infer from standards
    grade = ""

    # Reconstruct content dict from assignment
    content = {
        "title": original["title"],
        "instructions": "",
        "questions": original_content if isinstance(original_content, list) else [],
    }

    results = []
    for profile_id in req.profiles:
        profile = get_profile(profile_id, req.teacher_id)
        if not profile:
            results.append({"profile_id": profile_id, "error": "Profile not found"})
            continue

        # Apply modifications via Claude
        modified_content = apply_modifications(content, profile, subject, grade)

        # Render with SAME template and theme (dignity principle)
        student_html = render_template(template_id, modified_content, answer_key=False, theme=design_theme)
        answer_key_html = render_template(template_id, modified_content, answer_key=True, theme=design_theme)

        # Store as new assignment
        new_id = str(uuid4())
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO assignments
               (assignment_id, class_id, teacher_id, work_order_id, title,
                output_template_id, output_format, design_theme,
                standards_ids, questions, answer_key, status, file_paths)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'complete', %s)""",
            (
                new_id,
                str(original["class_id"]),
                str(original["teacher_id"]),
                f"ACCOM-{profile_id}-{req.assignment_id[:8]}",
                f"{original['title']} ({profile.get('name', profile_id)})",
                template_id,  # SAME template
                original.get("output_format", "html"),
                design_theme,  # SAME theme
                Json(original.get("standards_ids", [])),
                Json(modified_content.get("questions", [])),
                Json({"accommodation": profile_id}),
                Json({"parent_assignment_id": req.assignment_id, "accommodation_profile": profile_id}),
            ),
        )
        conn.commit()
        cur.close()

        results.append({
            "profile_id": profile_id,
            "profile_name": profile.get("name", profile_id),
            "assignment_id": new_id,
            "question_count": len(modified_content.get("questions", [])),
            "status": "complete",
            "student_html": student_html,
            "answer_key_html": answer_key_html,
        })

    return {
        "parent_assignment_id": req.assignment_id,
        "accommodation_versions": results,
        "total_generated": sum(1 for r in results if r.get("status") == "complete"),
    }
