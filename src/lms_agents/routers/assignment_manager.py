"""Assignment Manager — class-based views, grading inbox, quick actions."""
import os
from datetime import date, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.auth import require_teacher, assert_owner_or_403

router = APIRouter(prefix="/manager", tags=["Assignment Manager"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


# --- Class-Based Views ---

@router.get("/classes")
async def list_classes(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """List teacher's classes with assignment counts."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM assignments WHERE class_id = c.class_id) as assignment_count,
                  (SELECT COUNT(*) FROM submissions s
                   JOIN assignments a ON s.assignment_id = a.assignment_id
                   WHERE a.class_id = c.class_id AND s.status = 'needs_review') as pending_review
           FROM classes c WHERE c.teacher_id = %s::uuid ORDER BY c.name""",
        (teacher_id,),
    )
    classes = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"classes": classes}


@router.get("/classes/{class_id}")
async def class_detail(
    class_id: UUID,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Class detail with current week summary."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM classes WHERE class_id = %s", (str(class_id),))
    cls = cur.fetchone()
    if not cls:
        cur.close()
        return JSONResponse({"error": "Class not found"}, status_code=404)
    assert_owner_or_403(teacher_id, cls["teacher_id"])

    # This week's assignments
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    cur.execute(
        """SELECT * FROM assignments
           WHERE class_id = %s AND assigned_date BETWEEN %s AND %s
           ORDER BY assigned_date, created_at""",
        (str(class_id), monday, friday),
    )
    week_assignments = [dict(r) for r in cur.fetchall()]
    cur.close()

    result = dict(cls)
    result["this_week"] = week_assignments
    return result


@router.get("/classes/{class_id}/week")
async def class_week_view(
    class_id: UUID,
    date_str: str = Query(None, alias="date"),
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Full week view with assignments by day."""
    target = date.fromisoformat(date_str) if date_str else date.today()
    monday = target - timedelta(days=target.weekday())

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT teacher_id FROM classes WHERE class_id = %s", (str(class_id),))
    cls = cur.fetchone()
    if not cls:
        cur.close()
        return JSONResponse({"error": "Class not found"}, status_code=404)
    assert_owner_or_403(teacher_id, cls["teacher_id"])

    days = {}
    for i in range(5):
        day_date = monday + timedelta(days=i)
        day_name = ["mon", "tue", "wed", "thu", "fri"][i]
        cur.execute(
            """SELECT assignment_id, title, output_template_id, status, assigned_date,
                      (SELECT COUNT(*) FROM submissions WHERE assignment_id = a.assignment_id) as submissions
               FROM assignments a
               WHERE class_id = %s AND assigned_date = %s
               ORDER BY created_at""",
            (str(class_id), day_date),
        )
        days[day_name] = {"date": day_date.isoformat(), "assignments": [dict(r) for r in cur.fetchall()]}

    cur.close()
    return {"class_id": str(class_id), "week_start": monday.isoformat(), "days": days}


@router.get("/classes/{class_id}/calendar")
async def class_calendar(
    class_id: UUID,
    month: str = Query(None),
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Month calendar: per-day assignments + school_calendar overlay (day_type, label, notes)."""
    if month:
        year, m = month.split("-")
        start = date(int(year), int(m), 1)
    else:
        start = date.today().replace(day=1)

    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    last_day = end - timedelta(days=1)

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT teacher_id FROM classes WHERE class_id = %s", (str(class_id),))
    cls = cur.fetchone()
    if not cls:
        cur.close()
        return JSONResponse({"error": "Class not found"}, status_code=404)
    assert_owner_or_403(teacher_id, cls["teacher_id"])

    # Assignments per day (full rows, not just counts)
    cur.execute(
        """SELECT assignment_id, title, output_template_id, status, assigned_date,
                  (SELECT COUNT(*) FROM submissions WHERE assignment_id = a.assignment_id) as submissions
           FROM assignments a
           WHERE class_id = %s AND assigned_date >= %s AND assigned_date < %s
           ORDER BY assigned_date, created_at""",
        (str(class_id), start, end),
    )
    assignments_by_date: dict[str, list[dict]] = {}
    for row in cur.fetchall():
        d = row["assigned_date"].isoformat()
        assignments_by_date.setdefault(d, []).append({
            "assignment_id": str(row["assignment_id"]),
            "title": row["title"],
            "output_template_id": row["output_template_id"],
            "status": row["status"],
            "submissions": row["submissions"],
        })

    # School calendar overlay for this teacher in the same month
    cur.execute(
        """SELECT date, day_type, label, notes
           FROM school_calendar
           WHERE teacher_id = %s AND date >= %s AND date < %s""",
        (teacher_id, start, end),
    )
    school_by_date: dict[str, dict] = {}
    for row in cur.fetchall():
        d = row["date"].isoformat()
        school_by_date[d] = {
            "day_type": row["day_type"],
            "label": row["label"],
            "notes": row["notes"],
            "is_school_day": row["day_type"] in ("school_day", "half_day"),
        }

    cur.close()

    # Merge into a single day-keyed dict for the entire month
    days: dict[str, dict] = {}
    cur_date = start
    while cur_date < end:
        key = cur_date.isoformat()
        days[key] = {
            "assignments": assignments_by_date.get(key, []),
            "school": school_by_date.get(key),
        }
        cur_date += timedelta(days=1)

    return {
        "class_id": str(class_id),
        "month": start.isoformat()[:7],
        "first_day": start.isoformat(),
        "last_day": last_day.isoformat(),
        "days": days,
    }


class SchoolDayUpsert(BaseModel):
    teacher_id: str = "00000000-0000-0000-0000-000000000001"
    day_type: str  # school_day | no_school | holiday | half_day | snow_day | professional_development | break
    notes: Optional[str] = None
    label: Optional[str] = None


@router.put("/school-calendar/{date_iso}")
async def upsert_school_day(
    date_iso: str,
    req: SchoolDayUpsert,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """
    Upsert a single day in the teacher's school calendar.
    Used by the Calendar tab's day-detail modal to toggle school status and save a per-day note.
    """
    try:
        target = date.fromisoformat(date_iso)
    except ValueError:
        return JSONResponse({"error": "Invalid date format, expected YYYY-MM-DD"}, status_code=400)

    valid_types = {"school_day", "no_school", "holiday", "half_day", "snow_day", "professional_development", "break"}
    if req.day_type not in valid_types:
        return JSONResponse({"error": f"day_type must be one of {sorted(valid_types)}"}, status_code=400)

    # Derive school_year from the date (Jul–Dec = year/year+1, Jan–Jun = year-1/year)
    if target.month >= 7:
        school_year = f"{target.year}-{target.year + 1}"
    else:
        school_year = f"{target.year - 1}-{target.year}"

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """INSERT INTO school_calendar (teacher_id, school_year, date, day_type, label, notes)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (teacher_id, date) DO UPDATE SET
             day_type = EXCLUDED.day_type,
             label = EXCLUDED.label,
             notes = EXCLUDED.notes,
             school_year = EXCLUDED.school_year
           RETURNING date, day_type, label, notes""",
        (teacher_id, school_year, target, req.day_type, req.label, req.notes),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    return {
        "date": row["date"].isoformat(),
        "day_type": row["day_type"],
        "label": row["label"],
        "notes": row["notes"],
        "is_school_day": row["day_type"] in ("school_day", "half_day"),
    }


# --- Grading Inbox ---

@router.get("/grading-inbox")
async def grading_inbox(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """All items needing grading across all classes."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Worksheet/scan submissions needing review
    cur.execute(
        """SELECT s.submission_id, s.student_name, s.submission_method, s.status, s.created_at,
                  a.title as assignment_title, a.output_template_id,
                  c.name as class_name, c.class_id,
                  'submission' as item_type
           FROM submissions s
           JOIN assignments a ON s.assignment_id = a.assignment_id
           LEFT JOIN classes c ON a.class_id = c.class_id
           WHERE a.teacher_id = %s::uuid AND s.status IN ('needs_review', 'pending')
           ORDER BY s.created_at ASC""",
        (teacher_id,),
    )
    submissions = [dict(r) for r in cur.fetchall()]

    # Interactive submissions that haven't been reviewed
    cur.execute(
        """SELECT isub.submission_id, isub.student_name, isub.percentage, isub.submitted_at as created_at,
                  ia.interactive_template_id as output_template_id,
                  'interactive' as item_type, 'submitted' as status,
                  ia.content_json->>'title' as assignment_title
           FROM interactive_submissions isub
           JOIN interactive_activities ia ON isub.activity_id = ia.activity_id
           WHERE ia.teacher_id = %s::uuid
           ORDER BY isub.submitted_at DESC LIMIT 50""",
        (teacher_id,),
    )
    interactive = [dict(r) for r in cur.fetchall()]

    cur.close()

    all_items = submissions + interactive
    all_items.sort(key=lambda x: str(x.get("created_at", "")))

    return {"items": all_items, "total": len(all_items)}


@router.get("/grading-inbox/count")
async def inbox_count(
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Badge count for sidebar."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT COUNT(*) as count FROM submissions s
           JOIN assignments a ON s.assignment_id = a.assignment_id
           WHERE a.teacher_id = %s::uuid AND s.status IN ('needs_review', 'pending')""",
        (teacher_id,),
    )
    count = cur.fetchone()["count"]
    cur.close()
    return {"count": count}


# --- Quick Actions ---

class RescheduleRequest(BaseModel):
    assigned_date: str


@router.post("/assignments/{assignment_id}/duplicate")
async def duplicate_assignment(
    assignment_id: UUID,
    target_class_id: str = Query(None),
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Copy an assignment to another class or week."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM assignments WHERE assignment_id = %s", (str(assignment_id),))
    orig = cur.fetchone()
    if not orig:
        cur.close()
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    assert_owner_or_403(teacher_id, orig["teacher_id"])
    if target_class_id:
        cur.execute("SELECT teacher_id FROM classes WHERE class_id = %s::uuid", (target_class_id,))
        target_cls = cur.fetchone()
        if not target_cls:
            cur.close()
            return JSONResponse({"error": "Target class not found"}, status_code=404)
        assert_owner_or_403(teacher_id, target_cls["teacher_id"])

    new_id = str(uuid4())
    target = target_class_id or str(orig["class_id"])
    cur2 = conn.cursor()
    cur2.execute(
        """INSERT INTO assignments
           (assignment_id, class_id, teacher_id, title, output_template_id, output_format,
            design_theme, standards_ids, questions, answer_key, status)
           VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'complete')""",
        (new_id, target, str(orig["teacher_id"]), f"{orig['title']} (Copy)",
         orig["output_template_id"], orig.get("output_format", "html"),
         orig.get("design_theme", "modern_clean"),
         Json(orig.get("standards_ids", [])), Json(orig.get("questions", [])),
         Json(orig.get("answer_key", {}))),
    )
    conn.commit()
    cur.close(); cur2.close()
    return {"assignment_id": new_id, "status": "duplicated"}


@router.post("/assignments/{assignment_id}/reschedule")
async def reschedule(
    assignment_id: UUID,
    req: RescheduleRequest,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Change assigned_date."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE assignments SET assigned_date = %s WHERE assignment_id = %s AND teacher_id = %s::uuid",
        (req.assigned_date, str(assignment_id), teacher_id),
    )
    if cur.rowcount == 0:
        cur.close()
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    conn.commit()
    cur.close()
    return {"status": "rescheduled"}


@router.post("/assignments/{assignment_id}/archive")
async def archive(
    assignment_id: UUID,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Archive an assignment."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE assignments SET status = 'archived' WHERE assignment_id = %s AND teacher_id = %s::uuid",
        (str(assignment_id), teacher_id),
    )
    if cur.rowcount == 0:
        cur.close()
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    conn.commit()
    cur.close()
    return {"status": "archived"}
