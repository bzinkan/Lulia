"""Classes CRUD routes — per-class context isolation for multi-grade teachers."""
import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

router = APIRouter(prefix="/classes", tags=["Classes"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


# --- Request models ---

class CreateClassRequest(BaseModel):
    teacher_id: str
    name: str
    grade_level: str
    subject: str
    period: Optional[str] = None
    school_year: Optional[str] = None


class UpdateClassRequest(BaseModel):
    name: Optional[str] = None
    grade_level: Optional[str] = None
    subject: Optional[str] = None
    period: Optional[str] = None
    template_prefs: Optional[dict] = None
    # Class-level accommodation defaults — pre-selected in the planner refiner
    # so a teacher whose roster needs ELL-Beginner every day doesn't have to
    # tick that box on every work order. An empty list disables the default.
    default_accommodations: Optional[list[str]] = None


# --- Endpoints ---

@router.post("/")
async def create_class(req: CreateClassRequest, conn=Depends(get_db)):
    """Create a new class for a teacher."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    class_id = str(uuid4())
    cur.execute(
        """INSERT INTO classes
           (class_id, teacher_id, name, grade_level, subject, period, school_year)
           VALUES (%s, %s::uuid, %s, %s, %s, %s, %s)
           RETURNING *""",
        (class_id, req.teacher_id, req.name, req.grade_level,
         req.subject, req.period, req.school_year),
    )
    row = dict(cur.fetchone())
    conn.commit()
    cur.close()
    return row


@router.get("/")
async def list_classes(
    teacher_id: str = Query(...),
    include_archived: bool = Query(False),
    conn=Depends(get_db),
):
    """List teacher's classes with content counts."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    archive_filter = "" if include_archived else "AND c.archived_at IS NULL"
    cur.execute(
        f"""SELECT c.*, t.state_code,
                (SELECT count(*) FROM assignments WHERE class_id = c.class_id) AS assignment_count,
                (SELECT count(*) FROM knowledge_sources WHERE class_id = c.class_id) AS upload_count,
                (SELECT count(*) FROM videos WHERE class_id = c.class_id) AS video_count
            FROM classes c
            LEFT JOIN teachers t ON c.teacher_id = t.teacher_id
            WHERE c.teacher_id = %s::uuid {archive_filter}
            ORDER BY c.created_at""",
        (teacher_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"classes": rows, "count": len(rows)}


@router.get("/{class_id}")
async def get_class(class_id: str, conn=Depends(get_db)):
    """Get a single class with content counts."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT c.*, t.state_code,
                (SELECT count(*) FROM assignments WHERE class_id = c.class_id) AS assignment_count,
                (SELECT count(*) FROM knowledge_sources WHERE class_id = c.class_id) AS upload_count,
                (SELECT count(*) FROM videos WHERE class_id = c.class_id) AS video_count
            FROM classes c
            LEFT JOIN teachers t ON c.teacher_id = t.teacher_id
            WHERE c.class_id = %s::uuid""",
        (class_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Class not found"}, status_code=404)
    return dict(row)


@router.put("/{class_id}")
async def update_class(class_id: str, req: UpdateClassRequest, conn=Depends(get_db)):
    """Update class details or template preferences."""
    sets = []
    params = []
    if req.name is not None:
        sets.append("name = %s")
        params.append(req.name)
    if req.grade_level is not None:
        sets.append("grade_level = %s")
        params.append(req.grade_level)
    if req.subject is not None:
        sets.append("subject = %s")
        params.append(req.subject)
    if req.period is not None:
        sets.append("period = %s")
        params.append(req.period)
    if req.template_prefs is not None:
        sets.append("template_prefs = %s")
        params.append(Json(req.template_prefs))
    if req.default_accommodations is not None:
        # Accept an empty list to mean "clear the defaults" — distinguishable
        # from `None` (field not supplied), which is why the check is `is not None`.
        sets.append("default_accommodations = %s")
        params.append(Json(req.default_accommodations))

    if not sets:
        return JSONResponse({"error": "No fields to update"}, status_code=400)

    sets.append("updated_at = NOW()")
    params.append(class_id)

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        f"""UPDATE classes SET {', '.join(sets)}
            WHERE class_id = %s::uuid
            RETURNING *""",
        params,
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    if not row:
        return JSONResponse({"error": "Class not found"}, status_code=404)
    return dict(row)


@router.post("/{class_id}/archive")
async def archive_class(class_id: str, conn=Depends(get_db)):
    """Soft-archive a class (set archived_at)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """UPDATE classes SET archived_at = NOW(), updated_at = NOW()
           WHERE class_id = %s::uuid RETURNING class_id, archived_at""",
        (class_id,),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    if not row:
        return JSONResponse({"error": "Class not found"}, status_code=404)
    return dict(row)


@router.post("/{class_id}/unarchive")
async def unarchive_class(class_id: str, conn=Depends(get_db)):
    """Restore an archived class."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """UPDATE classes SET archived_at = NULL, updated_at = NOW()
           WHERE class_id = %s::uuid RETURNING class_id, archived_at""",
        (class_id,),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    if not row:
        return JSONResponse({"error": "Class not found"}, status_code=404)
    return dict(row)
