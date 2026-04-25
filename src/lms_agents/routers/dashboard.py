"""
Dashboard home — one round-trip to feed every widget on the home page.

Why a consolidated endpoint:
    The dashboard home renders 6 widgets (HeroBanner, StatsGrid, TodaySchedule,
    WeeklyActivityChart, ClassMastery, RecentActivity) + an Upcoming events
    card. Six parallel fetches on first paint would burn connections, burst
    through the rate limiter, and make the waterfall chart look terrible
    behind a cold RDS. Consolidating them into one response keeps the
    interaction tight and lets TanStack Query cache a single key.

Shape (pseudocode):
    {
      teacher: { name, tier, credits_remaining, credits_purchased },
      stats:   { total_students, assignments_week, class_average_pct, credits_remaining },
      today:   { schedule: [...], plan_count, pending_grading_count },
      mastery: { week_delta_pct, subjects: [...] },
      weekly_activity: [{day_label, date, value}, ...],  # 7 days ending today
      recent_activity: [{text, time_ago, kind, ref_id, icon, accent}, ...],
      upcoming:        [{title, date, kind, color}, ...]
    }

All fields degrade gracefully: a teacher with no classes, no plans, no
assignments yields zeros and empty lists — widgets already handle that
shape.

Why this lives in its own router:
    It's the only endpoint that fans out across half a dozen domains, and
    isolating it makes the read-path easy to reason about and easy to swap
    out later (e.g., if we want to serve it from a materialised view).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from psycopg2.extras import RealDictCursor

from src.lms_agents.tools.db import get_connection as _pool_get_connection

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
log = logging.getLogger(__name__)


def get_db():
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

_SUBJECT_COLORS = {
    # Canonical subject → Retro Earth palette color token. Anything not in
    # this map falls back to a cycle across the base palette.
    "Mathematics": "var(--coral)",
    "Math": "var(--coral)",
    "Science": "var(--sage)",
    "ELA": "var(--mustard)",
    "English Language Arts": "var(--mustard)",
    "Reading": "var(--mustard)",
    "Writing": "var(--mustard)",
    "Social Studies": "var(--teal)",
    "History": "var(--teal)",
    "Art": "var(--dusty-pink)",
    "Music": "var(--dusty-pink)",
    "PE": "var(--sage)",
}
_PALETTE_CYCLE = [
    "var(--coral)", "var(--sage)", "var(--mustard)", "var(--teal)",
    "var(--dusty-pink)",
]


def _subject_color(subject: str, idx: int) -> str:
    return _SUBJECT_COLORS.get(subject or "", _PALETTE_CYCLE[idx % len(_PALETTE_CYCLE)])


def _humanize_delta(ts: datetime, now: datetime) -> str:
    """Produce "2 min ago" / "3 hrs ago" / "Yesterday" / "Apr 5"."""
    delta = now - ts
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        m = secs // 60
        return f"{m} min ago"
    if secs < 86_400:
        h = secs // 3600
        return f"{h} hr{'s' if h != 1 else ''} ago"
    if secs < 2 * 86_400:
        return "Yesterday"
    # Same year → "Apr 5", else "Apr 5, 2025".
    if ts.year == now.year:
        return ts.strftime("%b %-d") if hasattr(ts, "strftime") else str(ts.date())
    return ts.strftime("%b %-d, %Y")


def _kind_to_icon(kind: str) -> tuple[str, str]:
    """Map an activity kind to (icon filename, accent var) pairs that match
    the palette the widget already uses. Keeping this in the backend means
    the frontend doesn't have to keep two lists in sync."""
    return {
        "assignment_generated": ("document.png", "var(--sage)"),
        "assignment_graded":    ("check.png", "var(--coral)"),
        "plan_approved":        ("calendar.png", "var(--teal)"),
        "video_added":          ("clipboard.png", "var(--mustard)"),
        "game_completed":       ("gamepad.png", "var(--dusty-pink)"),
        "share_created":        ("document.png", "var(--teal)"),
    }.get(kind, ("document.png", "var(--sage)"))


# ----------------------------------------------------------------------------
# Endpoint
# ----------------------------------------------------------------------------

@router.get("/home")
async def dashboard_home(
    teacher_id: UUID = Query(..., description="The viewing teacher's UUID"),
    class_id: Optional[UUID] = Query(
        None,
        description=(
            "Optional: restrict today/stats/mastery to a single active class. "
            "When omitted, stats are aggregated across all of the teacher's "
            "non-archived classes."
        ),
    ),
    conn=Depends(get_db),
):
    """One-shot payload for the dashboard home page.

    Safe on cold accounts: returns zero-valued fields rather than 404s so
    the widgets always render their empty-state.
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)
    tid = str(teacher_id)
    cid = str(class_id) if class_id else None
    today = date.today()
    now = datetime.now()

    payload: dict[str, Any] = {
        "teacher": {},
        "stats": {},
        "today": {"schedule": [], "plan_count": 0, "pending_grading_count": 0},
        "mastery": {"week_delta_pct": 0, "subjects": []},
        "weekly_activity": [],
        "recent_activity": [],
        "upcoming": [],
    }

    # ---- teacher ----------------------------------------------------------
    cur.execute(
        """SELECT name, tier, credit_balance,
                  COALESCE(credits_purchased, 0) AS credits_purchased
           FROM teachers
           WHERE teacher_id = %s::uuid""",
        (tid,),
    )
    t = cur.fetchone()
    if not t:
        # Cold / unknown teacher — return a complete empty shell rather
        # than 404 so the dashboard can still render the empty state.
        return payload
    payload["teacher"] = dict(t)

    # ---- class set to scope aggregates over ------------------------------
    # Either a single class (when class_id is passed) or every non-archived
    # class the teacher owns. We'll need both the id list (for IN clauses)
    # and the (subject, name) metadata for per-subject mastery rollup.
    if cid:
        cur.execute(
            """SELECT class_id, name, subject, grade_level
               FROM classes
               WHERE teacher_id = %s::uuid
                 AND class_id = %s::uuid
                 AND archived_at IS NULL""",
            (tid, cid),
        )
    else:
        cur.execute(
            """SELECT class_id, name, subject, grade_level
               FROM classes
               WHERE teacher_id = %s::uuid
                 AND archived_at IS NULL
               ORDER BY created_at ASC""",
            (tid,),
        )
    classes = [dict(r) for r in cur.fetchall()]
    class_ids = [str(c["class_id"]) for c in classes]

    # ---- stats ------------------------------------------------------------
    # total_students: there's no enrollment table in this schema — "who is in
    # this class" is derived from the set of students who have submitted to
    # one of the class's assignments (same path analytics_crew uses, so the
    # number here matches what the per-class dashboards show).
    # assignments_week: assignments created in the last 7 days.
    # class_average_pct: avg(mastery_percentage) across student_mastery rows
    # for those same students.
    if class_ids:
        cur.execute(
            """SELECT COUNT(DISTINCT sub.student_id) AS n
               FROM submissions sub
               JOIN assignments a ON sub.assignment_id = a.assignment_id
               WHERE a.class_id = ANY(%s::uuid[])
                 AND sub.student_id IS NOT NULL""",
            (class_ids,),
        )
        row = cur.fetchone()
        total_students = int(row["n"]) if row and row["n"] is not None else 0
    else:
        total_students = 0

    # assignments in the last 7 days (inclusive of today)
    cur.execute(
        """SELECT COUNT(*) AS n
           FROM assignments
           WHERE teacher_id = %s::uuid
             AND created_at >= %s""",
        (tid, now - timedelta(days=7)),
    )
    row = cur.fetchone()
    assignments_week = int(row["n"]) if row and row["n"] is not None else 0

    # class_average: mean over all per-standard mastery_percentage that
    # belong to a submission on one of this teacher's assignments. Uses
    # the same path aggregate_class_data uses so the numbers match.
    class_avg_pct = 0.0
    if class_ids:
        cur.execute(
            """SELECT AVG(sm.mastery_percentage)::float AS avg_pct
               FROM student_mastery sm
               WHERE sm.student_id IN (
                 SELECT DISTINCT sub.student_id
                 FROM submissions sub
                 JOIN assignments a ON sub.assignment_id = a.assignment_id
                 WHERE a.class_id = ANY(%s::uuid[])
                   AND sub.student_id IS NOT NULL
               )""",
            (class_ids,),
        )
        row = cur.fetchone()
        if row and row["avg_pct"] is not None:
            class_avg_pct = round(float(row["avg_pct"]), 1)

    payload["stats"] = {
        "total_students": total_students,
        "assignments_week": assignments_week,
        "class_average_pct": class_avg_pct,
        "credits_remaining": (
            int(payload["teacher"].get("credit_balance") or 0)
            + int(payload["teacher"].get("credits_purchased") or 0)
        ),
    }

    # ---- today: schedule + pending grading -------------------------------
    # Approved plan(s) whose week window covers today's date. We extract the
    # daily_plans entry matching today's weekday from plan_data JSONB.
    weekday_key = today.strftime("%a").lower()  # "mon", "tue", ...
    schedule: list[dict] = []
    plan_count = 0
    if class_ids:
        cur.execute(
            """SELECT plan_id, class_id, plan_data
               FROM lesson_plans
               WHERE class_id = ANY(%s::uuid[])
                 AND status IN ('approved', 'generating', 'complete')
                 AND week_start_date IS NOT NULL
                 AND week_start_date <= %s
                 AND week_start_date + INTERVAL '6 days' >= %s""",
            (class_ids, today, today),
        )
        for plan_row in cur.fetchall():
            plan_data = plan_row["plan_data"] or {}
            daily = (plan_data or {}).get("daily_plans") or []
            # daily_plans entries use either 'day' ('mon') or 'date' (ISO).
            today_entry = None
            for dp in daily:
                day = (dp.get("day") or "").lower()
                date_str = dp.get("date") or ""
                if day == weekday_key or date_str == today.isoformat():
                    today_entry = dp
                    break
            if not today_entry:
                continue
            plan_count += 1
            # Pull the matching class's subject for nicer labels.
            subj = next(
                (c["subject"] for c in classes
                 if str(c["class_id"]) == str(plan_row["class_id"])),
                "",
            )
            for wo in (today_entry.get("work_orders") or []):
                schedule.append({
                    "subject": subj or wo.get("subject") or "",
                    "topic": wo.get("title") or wo.get("topic") or wo.get("output_template_id") or "",
                    "time": wo.get("time") or "",
                    "status": (wo.get("status") or ("done" if wo.get("confirmed") else "prep")),
                    "work_order_id": wo.get("work_order_id"),
                })

    # Pending grading: submissions awaiting teacher review on this teacher's
    # assignments. "needs_review" and "pending" both count.
    pending_grading_count = 0
    if class_ids:
        cur.execute(
            """SELECT COUNT(*) AS n
               FROM submissions sub
               JOIN assignments a ON sub.assignment_id = a.assignment_id
               WHERE a.teacher_id = %s::uuid
                 AND sub.status IN ('pending', 'needs_review')""",
            (tid,),
        )
        row = cur.fetchone()
        pending_grading_count = int(row["n"]) if row and row["n"] is not None else 0

    payload["today"] = {
        "schedule": schedule,
        "plan_count": plan_count,
        "pending_grading_count": pending_grading_count,
    }

    # ---- mastery ----------------------------------------------------------
    # Per-subject rollup: for each distinct subject across the teacher's
    # classes, compute avg(mastery_percentage) over students in those
    # classes. Week delta: class_avg_pct − the same aggregate evaluated
    # 7 days ago using standard_mastery_history if available, else 0.
    subjects_rollup: list[dict] = []
    if class_ids:
        cur.execute(
            """SELECT c.subject,
                      AVG(sm.mastery_percentage)::float AS avg_pct,
                      COUNT(DISTINCT sm.student_id) AS n_students
               FROM classes c
               LEFT JOIN submissions sub
                 ON sub.assignment_id IN (
                   SELECT assignment_id FROM assignments
                   WHERE class_id = c.class_id
                 )
               LEFT JOIN student_mastery sm ON sm.student_id = sub.student_id
               WHERE c.class_id = ANY(%s::uuid[])
               GROUP BY c.subject
               ORDER BY c.subject""",
            (class_ids,),
        )
        for i, row in enumerate(cur.fetchall()):
            subj = row["subject"] or "Other"
            pct_val = row["avg_pct"]
            pct = round(float(pct_val), 1) if pct_val is not None else 0.0
            subjects_rollup.append({
                "name": subj,
                "pct": pct,
                "color": _subject_color(subj, i),
            })

    # week delta: compare today's class_avg_pct with the same metric 7 days ago
    week_delta = 0
    if class_ids:
        cur.execute(
            """SELECT AVG(mastery_percent)::float AS p
               FROM standard_mastery_history
               WHERE class_id = ANY(%s::uuid[])
                 AND date = %s""",
            (class_ids, today - timedelta(days=7)),
        )
        row = cur.fetchone()
        if row and row["p"] is not None:
            week_delta = round(class_avg_pct - float(row["p"]), 1)

    payload["mastery"] = {
        "week_delta_pct": week_delta,
        "subjects": subjects_rollup,
    }

    # ---- weekly_activity --------------------------------------------------
    # Bucket count of assignments + games into the last 7 days (ending today).
    start = today - timedelta(days=6)
    cur.execute(
        """SELECT d::date AS day, 0 AS n
           FROM generate_series(%s::date, %s::date, '1 day') AS d""",
        (start, today),
    )
    buckets = {row["day"]: 0 for row in cur.fetchall()}

    # Assignments generated (one event per assignment).
    cur.execute(
        """SELECT (created_at AT TIME ZONE 'UTC')::date AS d, COUNT(*) AS n
           FROM assignments
           WHERE teacher_id = %s::uuid AND created_at >= %s
           GROUP BY 1""",
        (tid, start),
    )
    for row in cur.fetchall():
        if row["d"] in buckets:
            buckets[row["d"]] += int(row["n"])

    # Game sessions created. `game_sessions_v2` is the current live-games
    # table (teacher_id + created_at); the older `game_sessions` shell uses
    # host_teacher_id + started_at. Prefer v2; fall back defensively if the
    # migration order has diverged in some env.
    try:
        cur.execute(
            """SELECT (created_at AT TIME ZONE 'UTC')::date AS d, COUNT(*) AS n
               FROM game_sessions_v2
               WHERE teacher_id = %s::uuid AND created_at >= %s
               GROUP BY 1""",
            (tid, start),
        )
        for row in cur.fetchall():
            if row["d"] in buckets:
                buckets[row["d"]] += int(row["n"])
    except Exception as e:  # pragma: no cover — table missing in some envs
        conn.rollback()
        log.debug("weekly_activity: game_sessions_v2 skipped: %s", e)

    weekly: list[dict] = []
    for i in range(7):
        d = start + timedelta(days=i)
        weekly.append({
            "day_label": d.strftime("%a"),
            "date": d.isoformat(),
            "value": int(buckets.get(d, 0)),
        })
    payload["weekly_activity"] = weekly

    # ---- recent_activity --------------------------------------------------
    # Union the last handful of events from each domain table, ORDER BY ts DESC.
    # Kept to LIMIT 20 to keep the response small.
    activity: list[dict] = []

    cur.execute(
        """SELECT created_at AS ts, 'assignment_generated' AS kind,
                  assignment_id AS ref_id, title AS text
           FROM assignments
           WHERE teacher_id = %s::uuid
           ORDER BY created_at DESC
           LIMIT 10""",
        (tid,),
    )
    for row in cur.fetchall():
        icon, accent = _kind_to_icon(row["kind"])
        activity.append({
            "text": f"{row['text']} — generated" if row["text"] else "Assignment generated",
            "time_ago": _humanize_delta(row["ts"], now),
            "ts": row["ts"].isoformat() if row["ts"] else None,
            "kind": row["kind"],
            "ref_id": str(row["ref_id"]) if row["ref_id"] else None,
            "icon": icon,
            "accent": accent,
        })

    try:
        cur.execute(
            """SELECT approved_at AS ts, 'plan_approved' AS kind, plan_id AS ref_id
               FROM lesson_plans
               WHERE teacher_id = %s::uuid
                 AND status IN ('approved', 'complete')
                 AND approved_at IS NOT NULL
               ORDER BY approved_at DESC
               LIMIT 5""",
            (tid,),
        )
        for row in cur.fetchall():
            icon, accent = _kind_to_icon(row["kind"])
            activity.append({
                "text": "Weekly plan approved",
                "time_ago": _humanize_delta(row["ts"], now),
                "ts": row["ts"].isoformat() if row["ts"] else None,
                "kind": row["kind"],
                "ref_id": str(row["ref_id"]) if row["ref_id"] else None,
                "icon": icon,
                "accent": accent,
            })
    except Exception as e:  # pragma: no cover
        conn.rollback()
        log.debug("recent_activity: lesson_plans skipped: %s", e)

    # Sort combined activity by ts desc, keep top N.
    activity.sort(key=lambda a: a.get("ts") or "", reverse=True)
    payload["recent_activity"] = activity[:8]

    # ---- upcoming ---------------------------------------------------------
    # School calendar overlays in the next 14 days. Skip regular school_day
    # entries; surface holidays / special days that teachers care about.
    cur.execute(
        """SELECT date, day_type, label
           FROM school_calendar
           WHERE teacher_id = %s::uuid
             AND date BETWEEN %s AND %s
             AND day_type <> 'school_day'
             AND label IS NOT NULL AND label <> ''
           ORDER BY date ASC
           LIMIT 6""",
        (tid, today, today + timedelta(days=14)),
    )
    upcoming_colors = ["var(--coral)", "var(--sage)", "var(--mustard)", "var(--teal)"]
    for i, row in enumerate(cur.fetchall()):
        payload["upcoming"].append({
            "title": row["label"],
            "date": row["date"].isoformat(),
            "date_label": row["date"].strftime("%a, %b %-d") if hasattr(row["date"], "strftime") else str(row["date"]),
            "kind": row["day_type"],
            "color": upcoming_colors[i % len(upcoming_colors)],
        })

    cur.close()
    return payload
