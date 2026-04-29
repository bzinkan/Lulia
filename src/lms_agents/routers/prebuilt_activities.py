"""Prebuilt activity library routes."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from src.lms_agents.tools.auth import require_teacher
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from src.lms_agents.tools.prebuilt_activity_renderer import build_prebuilt_activity_html
from src.lms_agents.tools.prebuilt_activity_schema import STATUS_VALUES
from src.lms_agents.tools.structured_common import deploy_structured_activity


router = APIRouter(prefix="/prebuilt-activities", tags=["Prebuilt Activities"])


def get_db():
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


class UsePrebuiltActivityRequest(BaseModel):
    teacher_id: Optional[str] = None
    class_id: Optional[str] = None
    customizations: dict[str, Any] = Field(default_factory=dict)


def _json_safe(row: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    content = out.get("content") or {}
    out["title"] = content.get("title") or out.get("lesson_title") or out.get("activity_id")
    return out


def _activity_from_row(row: dict[str, Any]) -> dict[str, Any]:
    item = _json_safe(dict(row))
    content = item.get("content") or {}
    return {
        "activity_id": item["activity_id"],
        "title": content.get("title") or item.get("lesson_title"),
        "activity_type": item["activity_type"],
        "subject": item.get("subject"),
        "course": item.get("course"),
        "grade_level": item.get("grade_level"),
        "grade_band": item.get("grade_band"),
        "unit_number": item.get("unit_number"),
        "unit_title": item.get("unit_title"),
        "lesson_number": item.get("lesson_number"),
        "lesson_title": item.get("lesson_title"),
        "standards": item.get("standards") or [],
        "visual_surface": item.get("visual_surface") or {},
        "content": content,
        "study_mode": content.get("study_mode") or {},
        "practice_mode": content.get("practice_mode") or {},
        "checks": item.get("checks") or [],
        "reflection_prompt": item.get("reflection_prompt") or {},
        "customizable_fields": content.get("customizable_fields") or [],
        "tags": item.get("tags") or [],
        "difficulty": item.get("difficulty"),
        "estimated_minutes": item.get("estimated_minutes"),
        "status": item.get("status"),
        "source": item.get("source"),
        "version": item.get("version"),
    }


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _status_filter(status: Optional[str]) -> Optional[str]:
    if status in (None, ""):
        return "published"
    if status == "all":
        return None
    if status not in STATUS_VALUES:
        raise HTTPException(status_code=400, detail=f"Unsupported status '{status}'")
    return status


def _fetch_activity_or_404(conn, activity_id: str, *, status: Optional[str] = None) -> dict[str, Any]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where = ["activity_id = %s"]
        params: list[Any] = [activity_id]
        if status:
            where.append("status = %s")
            params.append(status)
        cur.execute(
            f"""SELECT * FROM prebuilt_activities
                WHERE {' AND '.join(where)}
                LIMIT 1""",
            params,
        )
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        raise HTTPException(status_code=404, detail="Prebuilt activity not found")
    return dict(row)


@router.get("")
async def list_prebuilt_activities(
    grade_level: Optional[str] = None,
    subject: Optional[str] = None,
    course: Optional[str] = None,
    unit_number: Optional[int] = None,
    activity_type: Optional[str] = None,
    standard_code: Optional[str] = None,
    tag: Optional[str] = None,
    status: Optional[str] = Query("published"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """List prebuilt activities with teacher-library filters."""
    status_value = _status_filter(status)
    wheres: list[str] = []
    params: list[Any] = []

    if status_value:
        wheres.append("status = %s")
        params.append(status_value)
    if grade_level:
        wheres.append("grade_level = %s")
        params.append(grade_level)
    if subject:
        wheres.append("LOWER(subject) = LOWER(%s)")
        params.append(subject)
    if course:
        wheres.append("LOWER(course) = LOWER(%s)")
        params.append(course)
    if unit_number is not None:
        wheres.append("unit_number = %s")
        params.append(unit_number)
    if activity_type:
        wheres.append("activity_type = %s")
        params.append(activity_type)
    if standard_code:
        wheres.append("standards::text ILIKE %s")
        params.append(f"%{standard_code}%")
    if tag:
        wheres.append("%s = ANY(tags)")
        params.append(tag)

    where_sql = f"WHERE {' AND '.join(wheres)}" if wheres else ""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(f"SELECT COUNT(*) AS total FROM prebuilt_activities {where_sql}", params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"""SELECT * FROM prebuilt_activities
                {where_sql}
                ORDER BY course, unit_number NULLS LAST, lesson_number NULLS LAST, activity_id
                LIMIT %s OFFSET %s""",
            [*params, limit, offset],
        )
        activities = [_json_safe(dict(row)) for row in cur.fetchall()]
    finally:
        cur.close()

    return {"activities": activities, "total": total}


@router.get("/courses/{course}/map")
async def course_map(
    course: str,
    status: Optional[str] = Query("published"),
    _teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Return a unit/lesson map for one prebuilt course."""
    status_value = _status_filter(status)
    wheres = ["LOWER(course) = LOWER(%s)"]
    params: list[Any] = [course]
    if status_value:
        wheres.append("status = %s")
        params.append(status_value)

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            f"""SELECT activity_id, unit_number, unit_title, lesson_number, lesson_title,
                       activity_type, standards, difficulty, estimated_minutes,
                       content->>'title' AS title
                FROM prebuilt_activities
                WHERE {' AND '.join(wheres)}
                ORDER BY unit_number NULLS LAST, lesson_number NULLS LAST, activity_id""",
            params,
        )
        rows = [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()

    units: dict[int, dict[str, Any]] = {}
    for row in rows:
        unit_key = row.get("unit_number") or 0
        unit = units.setdefault(
            unit_key,
            {
                "unit_number": row.get("unit_number"),
                "unit_title": row.get("unit_title"),
                "lessons": [],
            },
        )
        unit["lessons"].append(
            {
                "lesson_number": row.get("lesson_number"),
                "lesson_title": row.get("lesson_title"),
                "activity_id": row.get("activity_id"),
                "title": row.get("title") or row.get("lesson_title"),
                "activity_type": row.get("activity_type"),
                "standards": row.get("standards") or [],
                "difficulty": row.get("difficulty"),
                "estimated_minutes": row.get("estimated_minutes"),
            }
        )

    return {"course": course, "units": list(units.values())}


@router.get("/{activity_id}")
async def get_prebuilt_activity(
    activity_id: str,
    status: Optional[str] = Query("published"),
    _teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    status_value = _status_filter(status)
    return _activity_from_row(_fetch_activity_or_404(conn, activity_id, status=status_value))


@router.post("/{activity_id}/preview")
async def preview_prebuilt_activity(
    activity_id: str,
    status: Optional[str] = Query("published"),
    _teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Render preview HTML for a canonical prebuilt activity."""
    status_value = _status_filter(status)
    activity = _activity_from_row(_fetch_activity_or_404(conn, activity_id, status=status_value))
    return {"activity": activity, "html": build_prebuilt_activity_html(activity)}


@router.post("/{activity_id}/use")
async def use_prebuilt_activity(
    activity_id: str,
    req: UsePrebuiltActivityRequest,
    teacher_id: str = Depends(require_teacher),
    conn=Depends(get_db),
):
    """Copy a published prebuilt activity into the teacher-owned activity flow."""
    row = _fetch_activity_or_404(conn, activity_id, status="published")

    if req.class_id:
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT 1 FROM classes
                   WHERE class_id = %s::uuid AND teacher_id = %s::uuid""",
                (req.class_id, teacher_id),
            )
            if not cur.fetchone():
                return JSONResponse({"error": "Class not found"}, status_code=404)
        finally:
            cur.close()

    activity = _activity_from_row(row)
    if req.customizations:
        activity = _deep_merge(activity, req.customizations)

    html = build_prebuilt_activity_html(activity)
    title = activity.get("title") or activity.get("lesson_title") or activity["activity_id"]
    result = deploy_structured_activity(
        html=html,
        template_id=activity.get("activity_type") or "prebuilt_activity",
        title=title,
        teacher_id=teacher_id,
        class_id=req.class_id,
        standards=activity.get("standards") or [],
        content_summary={
            "source": "prebuilt_activity",
            "source_prebuilt_activity_id": activity_id,
            "title": title,
            "subject": activity.get("subject"),
            "course": activity.get("course"),
        },
        full_data=activity,
        questions_for_assignment=activity.get("checks") or [],
    )
    result["source_prebuilt_activity_id"] = activity_id
    return result
