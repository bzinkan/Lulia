"""Sharing & Remix routes — share assignments publicly and let others copy them."""
import os
import random
import string
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.auth import require_teacher, assert_owner_or_403

router = APIRouter(prefix="/share", tags=["Sharing"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _gen_slug(title: str) -> str:
    """Generate a URL-friendly slug."""
    base = title.lower()[:30].strip()
    base = "".join(c if c.isalnum() or c == " " else "" for c in base).strip().replace(" ", "-")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{base}-{suffix}"


@router.post("/assignment/{assignment_id}")
async def share_assignment(
    assignment_id: UUID,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Make an assignment public. Returns share URL."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM assignments WHERE assignment_id = %s", (str(assignment_id),))
    a = cur.fetchone()
    if not a:
        cur.close()
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    assert_owner_or_403(teacher_id, a["teacher_id"])

    slug = _gen_slug(a["title"])
    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE assignments SET is_shared = true, share_slug = %s WHERE assignment_id = %s",
        (slug, str(assignment_id)),
    )
    conn.commit()
    cur.close(); cur2.close()
    return {"share_slug": slug, "share_url": f"/share/{slug}", "status": "shared"}


@router.delete("/assignment/{assignment_id}")
async def unshare_assignment(
    assignment_id: UUID,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Remove public sharing."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE assignments SET is_shared = false, share_slug = NULL WHERE assignment_id = %s AND teacher_id = %s::uuid",
        (str(assignment_id), teacher_id),
    )
    if cur.rowcount == 0:
        cur.close()
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    conn.commit(); cur.close()
    return {"status": "unshared"}


@router.get("/{slug}")
async def view_shared(slug: str, conn=Depends(get_db)):
    """Public endpoint to view a shared assignment."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT a.assignment_id, a.title, a.output_template_id, a.standards_ids,
                  a.questions, a.remix_count, a.created_at,
                  t.name as teacher_name, t.school_name
           FROM assignments a
           LEFT JOIN teachers t ON a.teacher_id = t.teacher_id
           WHERE a.share_slug = %s AND a.is_shared = true""",
        (slug,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Shared content not found"}, status_code=404)
    return dict(row)


@router.post("/{slug}/remix")
async def remix_assignment(
    slug: str,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Copy a shared assignment to the current teacher's account."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM assignments WHERE share_slug = %s AND is_shared = true", (slug,))
    orig = cur.fetchone()
    if not orig:
        cur.close()
        return JSONResponse({"error": "Shared content not found"}, status_code=404)

    new_id = str(uuid4())
    cur2 = conn.cursor()
    cur2.execute(
        """INSERT INTO assignments
           (assignment_id, teacher_id, title, output_template_id, output_format,
            design_theme, standards_ids, questions, answer_key, status, original_assignment_id)
           VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, 'complete', %s)""",
        (new_id, teacher_id, f"{orig['title']} (Remix)",
         orig["output_template_id"], orig.get("output_format", "html"),
         orig.get("design_theme", "modern_clean"),
         Json(orig.get("standards_ids", [])), Json(orig.get("questions", [])),
         Json(orig.get("answer_key", {})), str(orig["assignment_id"])),
    )
    # Increment remix count
    cur2.execute(
        "UPDATE assignments SET remix_count = COALESCE(remix_count, 0) + 1 WHERE assignment_id = %s",
        (str(orig["assignment_id"]),),
    )
    conn.commit(); cur.close(); cur2.close()
    return {"assignment_id": new_id, "status": "remixed"}


@router.get("/popular/list")
async def popular_shared(
    subject: str = Query(None),
    conn=Depends(get_db),
):
    """List trending shared content."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    conditions = ["a.is_shared = true"]
    params = []
    if subject:
        conditions.append("a.standards_ids::text ILIKE %s")
        params.append(f"%{subject}%")
    where = " AND ".join(conditions)
    params.append(20)
    cur.execute(
        f"""SELECT a.assignment_id, a.title, a.output_template_id, a.standards_ids,
                   a.share_slug, a.remix_count, a.created_at,
                   t.name as teacher_name
            FROM assignments a
            LEFT JOIN teachers t ON a.teacher_id = t.teacher_id
            WHERE {where}
            ORDER BY a.remix_count DESC, a.created_at DESC LIMIT %s""",
        params,
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"shared": rows}
