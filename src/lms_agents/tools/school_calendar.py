"""
School Calendar — tracks school days, holidays, PD days, half-days.

The Planner queries this to know which days in a week are actually
school days, so it doesn't generate lesson plans for holidays.

Teachers can upload their school calendar (PDF/CSV) or manually mark
days. The calendar is per-teacher (different schools have different
schedules).
"""
import json
import logging
import os
import re
from datetime import date, timedelta
from typing import Optional

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

HAIKU = "claude-haiku-4-5-20251001"

DAY_TYPES = {
    "school_day",
    "holiday",
    "professional_development",
    "half_day",
    "snow_day",
    "break",
    "no_school",
}


def get_school_days(
    teacher_id: str,
    week_start: date,
    week_end: date | None = None,
) -> list[dict]:
    """
    Get school calendar entries for a date range.

    Returns a list of dicts with {date, day_type, label, is_school_day, is_half_day}.
    Dates not in the calendar are assumed to be school days (Mon-Fri).
    Weekends are always non-school days.
    """
    if week_end is None:
        week_end = week_start + timedelta(days=4)  # Mon-Fri

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """SELECT date, day_type, label, notes
               FROM school_calendar
               WHERE teacher_id = %s::uuid
                 AND date BETWEEN %s AND %s
               ORDER BY date ASC""",
            (teacher_id, week_start, week_end),
        )
        cal_entries = {str(r["date"]): dict(r) for r in cur.fetchall()}
    finally:
        cur.close()
        conn.close()

    # Build result for each day in range
    result = []
    current = week_start
    while current <= week_end:
        day_of_week = current.weekday()  # 0=Mon, 6=Sun
        date_str = str(current)

        if day_of_week >= 5:
            # Weekend — always non-school
            result.append({
                "date": date_str,
                "day_type": "weekend",
                "label": "Weekend",
                "is_school_day": False,
                "is_half_day": False,
            })
        elif date_str in cal_entries:
            entry = cal_entries[date_str]
            dt = entry["day_type"]
            result.append({
                "date": date_str,
                "day_type": dt,
                "label": entry.get("label") or dt.replace("_", " ").title(),
                "is_school_day": dt in ("school_day", "half_day"),
                "is_half_day": dt == "half_day",
            })
        else:
            # Not in calendar — assume school day
            result.append({
                "date": date_str,
                "day_type": "school_day",
                "label": None,
                "is_school_day": True,
                "is_half_day": False,
            })

        current += timedelta(days=1)

    return result


def filter_school_days_for_planner(
    teacher_id: str,
    week_start: date,
    selected_days: list[str],
) -> tuple[list[str], list[dict]]:
    """
    Filter selected_days to only include actual school days.

    Returns:
        (filtered_days, non_school_entries)
        filtered_days: ['mon', 'wed', 'thu', 'fri'] (after removing holidays)
        non_school_entries: [{'day': 'tue', 'label': 'Veterans Day'}]
    """
    day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    week_end = week_start + timedelta(days=4)
    cal = get_school_days(teacher_id, week_start, week_end)

    filtered = []
    non_school = []

    for entry in cal:
        entry_date = date.fromisoformat(entry["date"])
        day_idx = entry_date.weekday()
        if day_idx >= 5:
            continue
        day_name = day_names[day_idx]

        if day_name not in selected_days:
            continue

        if entry["is_school_day"]:
            filtered.append(day_name)
        else:
            non_school.append({
                "day": day_name,
                "label": entry.get("label") or "No School",
                "day_type": entry["day_type"],
            })

    return filtered, non_school


def parse_school_calendar_with_haiku(
    text: str,
    school_year: str = "2025-2026",
) -> list[dict]:
    """
    Use Claude Haiku to extract dates and day types from a school calendar document.

    Returns list of {date, day_type, label}.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    system = (
        "You are a school calendar parser. You extract dates and their types "
        "(holiday, professional development, half day, break, no school) from "
        "school calendar documents. Only extract NON-SCHOOL days — do not list "
        "regular school days. Output clean JSON."
    )

    user = f"""Extract all non-school days from this school calendar for the {school_year} school year.

--- DOCUMENT ---
{text[:16000]}
--- END ---

Return a JSON array:
[
  {{"date": "2025-09-01", "day_type": "holiday", "label": "Labor Day"}},
  {{"date": "2025-11-27", "day_type": "break", "label": "Thanksgiving Break"}},
  {{"date": "2025-11-28", "day_type": "break", "label": "Thanksgiving Break"}}
]

day_type must be one of: holiday, professional_development, half_day, snow_day, break, no_school

Rules:
- Only include dates that are NOT regular school days for students
- Teacher workdays, PD days, and "No Students" days all count as non-school days (use professional_development)
- Holidays where schools are closed → "holiday"
- Vacation periods (Winter Recess, Spring Break, Thanksgiving Break) → "break"
- CRITICAL: For any date RANGE, you MUST enumerate EVERY single date in the range as its own entry.
  Examples:
    "Aug 13-14" → output TWO entries: Aug 13 AND Aug 14
    "Dec 22-Jan 2 Winter Recess (10 days)" → output ENTRIES FOR EACH DATE: Dec 22, 23, 24, 25, 26, 29, 30, 31, Jan 1, Jan 2 (plus any weekdays in between)
    "Mar 23-27 Spring Break" → output FIVE entries: Mar 23, 24, 25, 26, 27
  Do NOT output a single entry for a range. If you see a dash, en-dash, or "through" between two dates, expand.
- Year inference: dates from Aug-Dec use the first year of "{school_year}"; dates from Jan-Jul use the second year.
- Use ISO format (YYYY-MM-DD) for every date
- Include a descriptive label for each entry (e.g., "Winter Recess Day 3", "Christmas Day", "PD Day")
- SKIP these — they are regular school days:
    "First Day of School", "Schools Reopen", "Midterm Week", "End of Quarter", "Last day for Students"
- Respond with ONLY the JSON array, no preamble"""

    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text_resp = resp.content[0].text

        try:
            return json.loads(text_resp)
        except json.JSONDecodeError:
            match = re.search(r"\[[\s\S]*\]", text_resp)
            if match:
                return json.loads(match.group())
            return []
    except Exception as e:
        log.error(f"[SchoolCal] Haiku parse failed: {e}")
        return []


def store_school_calendar(
    teacher_id: str,
    entries: list[dict],
    school_year: str = "2025-2026",
) -> int:
    """Store parsed school calendar entries in the database."""
    conn = get_connection()
    cur = conn.cursor()
    stored = 0
    try:
        for entry in entries:
            dt = entry.get("day_type", "no_school")
            if dt not in DAY_TYPES:
                dt = "no_school"
            try:
                cur.execute(
                    """INSERT INTO school_calendar
                       (teacher_id, school_year, date, day_type, label)
                       VALUES (%s::uuid, %s, %s, %s, %s)
                       ON CONFLICT (teacher_id, date) DO UPDATE
                       SET day_type = EXCLUDED.day_type,
                           label = EXCLUDED.label""",
                    (teacher_id, school_year, entry["date"], dt, entry.get("label")),
                )
                stored += 1
            except Exception as e:
                log.warning(f"[SchoolCal] Failed to store {entry.get('date')}: {e}")
                conn.rollback()
                continue
        conn.commit()
        log.info(f"[SchoolCal] Stored {stored} calendar entries for teacher {teacher_id}")
    finally:
        cur.close()
        conn.close()
    return stored
