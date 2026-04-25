"""
Calendar routes — curriculum calendar CRUD, CSV import, Google/Classroom sync, PDF.

The curriculum calendar stores weekly pacing data: which units, topics, and
standards are scheduled each week. Populated via curriculum upload (Claude parsing),
CSV import, or manual entry.
"""
import os
from datetime import date
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel

from src.lms_agents.tools.curriculum_importer import import_csv_pacing

router = APIRouter(prefix="/calendar", tags=["Calendar"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


class CalendarEntryCreate(BaseModel):
    week_number: int
    unit_name: str | None = None
    topic: str | None = None
    standards_scheduled: list[str] = []
    is_assessment_week: bool = False
    pacing_notes: str | None = None
    week_start_date: date | None = None


class CalendarEntryUpdate(BaseModel):
    week_number: int | None = None
    unit_name: str | None = None
    topic: str | None = None
    standards_scheduled: list[str] | None = None
    is_assessment_week: bool | None = None
    pacing_notes: str | None = None
    week_start_date: date | None = None


@router.get("/{class_id}")
async def get_curriculum_calendar(
    class_id: UUID,
    conn=Depends(get_db),
):
    """Get the full curriculum calendar for a class, ordered by week."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT calendar_id, class_id, week_number, week_start_date,
                  unit_name, topic, standards_scheduled, pacing_notes,
                  is_assessment_week, source_upload_id
           FROM curriculum_calendar
           WHERE class_id = %s
           ORDER BY week_number ASC""",
        (str(class_id),),
    )
    rows = cur.fetchall()
    cur.close()
    return {"class_id": str(class_id), "weeks": [dict(r) for r in rows]}


@router.post("/{class_id}/manual")
async def add_calendar_entry(
    class_id: UUID,
    entry: CalendarEntryCreate,
    conn=Depends(get_db),
):
    """Manually add a single calendar entry for a class."""
    cur = conn.cursor()
    calendar_id = str(uuid4())
    cur.execute(
        """INSERT INTO curriculum_calendar
           (calendar_id, class_id, week_number, week_start_date,
            unit_name, topic, standards_scheduled, pacing_notes,
            is_assessment_week)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING calendar_id""",
        (
            calendar_id, str(class_id), entry.week_number,
            entry.week_start_date, entry.unit_name, entry.topic,
            Json(entry.standards_scheduled), entry.pacing_notes,
            entry.is_assessment_week,
        ),
    )
    conn.commit()
    cur.close()
    return {"calendar_id": calendar_id, "status": "created"}


@router.put("/{calendar_id}")
async def update_calendar_entry(
    calendar_id: UUID,
    entry: CalendarEntryUpdate,
    conn=Depends(get_db),
):
    """Edit an existing calendar entry."""
    cur = conn.cursor()

    # Build dynamic SET clause for non-None fields
    updates = []
    params = []
    if entry.week_number is not None:
        updates.append("week_number = %s")
        params.append(entry.week_number)
    if entry.unit_name is not None:
        updates.append("unit_name = %s")
        params.append(entry.unit_name)
    if entry.topic is not None:
        updates.append("topic = %s")
        params.append(entry.topic)
    if entry.standards_scheduled is not None:
        updates.append("standards_scheduled = %s")
        params.append(Json(entry.standards_scheduled))
    if entry.is_assessment_week is not None:
        updates.append("is_assessment_week = %s")
        params.append(entry.is_assessment_week)
    if entry.pacing_notes is not None:
        updates.append("pacing_notes = %s")
        params.append(entry.pacing_notes)
    if entry.week_start_date is not None:
        updates.append("week_start_date = %s")
        params.append(entry.week_start_date)

    if not updates:
        return JSONResponse({"error": "No fields to update"}, status_code=400)

    params.append(str(calendar_id))
    sql = f"UPDATE curriculum_calendar SET {', '.join(updates)} WHERE calendar_id = %s"
    cur.execute(sql, params)

    if cur.rowcount == 0:
        cur.close()
        return JSONResponse({"error": "Calendar entry not found"}, status_code=404)

    conn.commit()
    cur.close()
    return {"calendar_id": str(calendar_id), "status": "updated"}


@router.delete("/{calendar_id}")
async def delete_calendar_entry(
    calendar_id: UUID,
    conn=Depends(get_db),
):
    """Delete a calendar entry."""
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM curriculum_calendar WHERE calendar_id = %s",
        (str(calendar_id),),
    )
    if cur.rowcount == 0:
        cur.close()
        return JSONResponse({"error": "Calendar entry not found"}, status_code=404)
    conn.commit()
    cur.close()
    return {"status": "deleted"}


@router.post("/{class_id}/import-csv")
async def import_csv(
    class_id: UUID,
    file: UploadFile = File(...),
    week_start: Optional[str] = Form(None),
):
    """
    Import pacing data from CSV file.

    Expected columns: week_number, unit_name, topic, standards, assessment, notes
    """
    content = await file.read()
    csv_text = content.decode("utf-8", errors="replace")

    start_date = None
    if week_start:
        try:
            start_date = date.fromisoformat(week_start)
        except ValueError:
            return JSONResponse({"error": "Invalid week_start date format (use YYYY-MM-DD)"}, status_code=400)

    result = import_csv_pacing(
        csv_content=csv_text,
        class_id=str(class_id),
        week_start=start_date,
    )
    result["class_id"] = str(class_id)
    return result


# --- Future Phase 8: Google integration stubs ---

@router.post("/sync-google")
async def sync_google_calendar():
    """Sync to Google Calendar."""
    return {"status": "stub"}


@router.post("/sync-classroom")
async def sync_classroom():
    """Organize Classroom topics."""
    return {"status": "stub"}


@router.get("/pdf")
async def calendar_pdf():
    """Generate visual calendar PDF."""
    return {"status": "stub"}
