"""
Google Calendar Sync — pushes lesson plan events to teacher's Google Calendar.
"""
import logging

from src.lms_agents.tools.google_auth import get_credentials

log = logging.getLogger(__name__)

# Subject-based color IDs (Google Calendar has 11 colors)
SUBJECT_COLORS = {
    "Mathematics": "6",  # tangerine
    "Math": "6",
    "ELA": "9",  # blueberry
    "English Language Arts": "9",
    "Science": "2",  # sage
    "Social Studies": "5",  # banana
}


def sync_plan_to_calendar(
    teacher_id: str,
    plan_data: dict,
    calendar_id: str = "primary",
) -> list[dict]:
    """
    Sync a lesson plan to Google Calendar.
    Each day becomes a calendar event.
    Returns list of created event IDs.
    """
    credentials = get_credentials(teacher_id)
    if not credentials:
        raise ValueError("Teacher not connected to Google")

    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=credentials)
    events_created = []

    daily_plans = plan_data.get("daily_plans", [])
    subject = plan_data.get("subject", "")
    color_id = SUBJECT_COLORS.get(subject, "1")

    for dp in daily_plans:
        day_date = dp.get("date", "")
        title = dp.get("title", "")
        standards = dp.get("standards", [])
        procedures = dp.get("procedures", [])
        work_orders = dp.get("work_orders", [])

        # Build description
        desc_parts = [f"Standards: {', '.join(standards)}"]
        for proc in procedures:
            desc_parts.append(f"• {proc.get('phase', '')} ({proc.get('duration_minutes', 0)}m): {proc.get('description', '')}")
        if work_orders:
            materials = [f"{wo.get('output_template_id', '')} ({wo.get('question_count', '')}q)" for wo in work_orders]
            desc_parts.append(f"\nMaterials: {', '.join(materials)}")

        event = {
            "summary": f"{subject} — {title}",
            "description": "\n".join(desc_parts),
            "start": {"date": day_date},
            "end": {"date": day_date},
            "colorId": color_id,
        }

        try:
            result = service.events().insert(
                calendarId=calendar_id, body=event
            ).execute()
            events_created.append({
                "day": dp.get("day", ""),
                "event_id": result["id"],
                "link": result.get("htmlLink", ""),
            })
        except Exception as e:
            log.warning(f"Failed to create calendar event for {day_date}: {e}")
            events_created.append({
                "day": dp.get("day", ""),
                "error": str(e),
            })

    log.info(f"[Calendar] Created {len(events_created)} events")
    return events_created
