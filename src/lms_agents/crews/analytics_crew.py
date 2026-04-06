"""
Analytics Crew — aggregates grading data, generates insights, produces reports.

Chain: Data Aggregator → Insight Agent → Report Agent
Feeds back into Planner for adaptive lesson planning.
"""
import json
import logging
import os
import re
from datetime import date, timedelta
from uuid import uuid4

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)
HAIKU = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Agent 1: Data Aggregator
# ---------------------------------------------------------------------------

def aggregate_class_data(class_id: str) -> dict:
    """Aggregate mastery data for a class."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get students with mastery data linked to this class's assignments
    cur.execute(
        """SELECT DISTINCT sm.student_id, sm.standard_id,
                  sm.total_questions, sm.correct_questions, sm.mastery_percentage, sm.trend
           FROM student_mastery sm
           WHERE sm.student_id IN (
               SELECT DISTINCT sub.student_id FROM submissions sub
               JOIN assignments a ON sub.assignment_id = a.assignment_id
               WHERE a.class_id = %s AND sub.student_id IS NOT NULL
           )
           ORDER BY sm.standard_id""",
        (class_id,),
    )
    mastery_rows = [dict(r) for r in cur.fetchall()]

    # Standards summary
    by_standard: dict[str, dict] = {}
    by_student: dict[str, dict] = {}

    for row in mastery_rows:
        std = row["standard_id"]
        sid = str(row["student_id"]) if row["student_id"] else "unknown"

        if std not in by_standard:
            by_standard[std] = {"total_q": 0, "correct_q": 0, "student_count": 0}
        by_standard[std]["total_q"] += row["total_questions"]
        by_standard[std]["correct_q"] += row["correct_questions"]
        by_standard[std]["student_count"] += 1

        if sid not in by_student:
            by_student[sid] = {"total_q": 0, "correct_q": 0, "standards": []}
        by_student[sid]["total_q"] += row["total_questions"]
        by_student[sid]["correct_q"] += row["correct_questions"]
        by_student[sid]["standards"].append(std)

    # Calculate percentages
    standards_summary = []
    for std, data in by_standard.items():
        pct = round(data["correct_q"] / max(data["total_q"], 1) * 100, 1)
        status = "mastered" if pct >= 80 else "developing" if pct >= 60 else "needs_work"
        standards_summary.append({
            "standard_code": std,
            "mastery_percent": pct,
            "status": status,
            "total_questions": data["total_q"],
            "students_assessed": data["student_count"],
        })

    students_summary = []
    for sid, data in by_student.items():
        pct = round(data["correct_q"] / max(data["total_q"], 1) * 100, 1)
        students_summary.append({
            "student_id": sid,
            "average_mastery": pct,
            "total_questions": data["total_q"],
            "standards_count": len(set(data["standards"])),
            "struggling": pct < 65,
        })

    # Overall class average
    all_pcts = [s["mastery_percent"] for s in standards_summary]
    class_average = round(sum(all_pcts) / max(len(all_pcts), 1), 1) if all_pcts else 0

    struggling_standards = [s for s in standards_summary if s["mastery_percent"] < 70]
    mastered_standards = [s for s in standards_summary if s["mastery_percent"] >= 80]
    struggling_students = [s for s in students_summary if s["struggling"]]

    # Submission stats
    cur.execute(
        """SELECT COUNT(*) as total FROM submissions sub
           JOIN assignments a ON sub.assignment_id = a.assignment_id
           WHERE a.class_id = %s""",
        (class_id,),
    )
    total_submissions = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return {
        "class_id": class_id,
        "class_average": class_average,
        "total_students": len(students_summary),
        "total_standards": len(standards_summary),
        "total_submissions": total_submissions,
        "mastered_count": len(mastered_standards),
        "needs_work_count": len(struggling_standards),
        "standards": sorted(standards_summary, key=lambda x: x["mastery_percent"]),
        "students": sorted(students_summary, key=lambda x: x["average_mastery"]),
        "struggling_standards": struggling_standards,
        "struggling_students": struggling_students,
        "mastered_standards": mastered_standards,
    }


# ---------------------------------------------------------------------------
# Agent 2: Insight Agent
# ---------------------------------------------------------------------------

def generate_insights(analytics_data: dict) -> list[dict]:
    """Use Claude Haiku to generate plain-language insights and recommendations."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_insights(analytics_data)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=1024,
            messages=[{"role": "user", "content": (
                f"You are a data-driven instructional coach. Analyze this class performance data and generate 3-5 actionable insights.\n\n"
                f"Class average: {analytics_data['class_average']}%\n"
                f"Standards mastered: {analytics_data['mastered_count']}/{analytics_data['total_standards']}\n"
                f"Struggling standards: {json.dumps([s['standard_code'] + ' (' + str(s['mastery_percent']) + '%)' for s in analytics_data.get('struggling_standards', [])])}\n"
                f"Struggling students: {len(analytics_data.get('struggling_students', []))}\n\n"
                f"Generate a JSON array of insights:\n"
                f'[{{"type": "celebration|concern|action|suggestion", "message": "plain language insight", "action": "specific recommended action", "priority": "high|medium|low"}}]\n'
                f"Respond with ONLY the JSON array."
            )}],
        )
        text = resp.content[0].text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        log.warning(f"Insight generation failed: {e}")

    return _fallback_insights(analytics_data)


def _fallback_insights(data: dict) -> list[dict]:
    """Generate basic insights without LLM."""
    insights = []
    if data["class_average"] >= 80:
        insights.append({"type": "celebration", "message": f"Class average is {data['class_average']}% — great progress!", "action": "Consider moving to more advanced content", "priority": "low"})
    elif data["class_average"] < 65:
        insights.append({"type": "concern", "message": f"Class average is {data['class_average']}% — below target", "action": "Schedule review sessions for struggling standards", "priority": "high"})

    for s in data.get("struggling_standards", [])[:3]:
        insights.append({"type": "action", "message": f"{s['standard_code']} is at {s['mastery_percent']}% — needs re-teaching", "action": f"Add re-teach day for {s['standard_code']}", "priority": "high"})

    if data.get("struggling_students"):
        insights.append({"type": "suggestion", "message": f"{len(data['struggling_students'])} students are below 65%", "action": "Consider generating accommodation versions", "priority": "medium"})

    return insights


# ---------------------------------------------------------------------------
# Agent 3: Report Agent (generates analytics HTML)
# ---------------------------------------------------------------------------

def generate_class_report(class_id: str, analytics_data: dict, insights: list) -> str:
    """Generate a printable class report."""
    from src.lms_agents.tools.template_renderer import _base_css

    standards_html = ""
    for s in analytics_data.get("standards", []):
        color = "#059669" if s["mastery_percent"] >= 80 else "#D97706" if s["mastery_percent"] >= 60 else "#EF4444"
        bar_width = min(s["mastery_percent"], 100)
        standards_html += f"""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
          <span style="min-width:80px;font-size:11px;font-weight:600;color:var(--t-text);">{s['standard_code']}</span>
          <div style="flex:1;height:16px;background:var(--t-border-light);border-radius:8px;overflow:hidden;">
            <div style="width:{bar_width}%;height:100%;background:{color};border-radius:8px;"></div>
          </div>
          <span style="min-width:40px;font-size:11px;font-weight:600;color:{color};">{s['mastery_percent']}%</span>
        </div>"""

    insights_html = ""
    for ins in insights[:5]:
        icon = "✓" if ins["type"] == "celebration" else "⚠" if ins["type"] == "concern" else "→"
        insights_html += f'<div style="margin-bottom:6px;font-size:12px;color:var(--t-text-secondary);"><span style="font-weight:600;">{icon}</span> {ins["message"]}</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>Class Analytics Report</h1><div class="subtitle">Generated {date.today().isoformat()}</div></div></div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px;">
    <div style="background:var(--t-primary-bg);border-radius:10px;padding:10px;text-align:center;"><div style="font-size:9px;color:var(--t-text-muted);text-transform:uppercase;">Class Average</div><div style="font-size:24px;font-weight:700;color:var(--t-primary);">{analytics_data['class_average']}%</div></div>
    <div style="background:var(--t-success-bg);border-radius:10px;padding:10px;text-align:center;"><div style="font-size:9px;color:var(--t-text-muted);text-transform:uppercase;">Mastered</div><div style="font-size:24px;font-weight:700;color:var(--t-success);">{analytics_data['mastered_count']}</div></div>
    <div style="background:#FEF3C7;border-radius:10px;padding:10px;text-align:center;"><div style="font-size:9px;color:var(--t-text-muted);text-transform:uppercase;">Needs Work</div><div style="font-size:24px;font-weight:700;color:#D97706;">{analytics_data['needs_work_count']}</div></div>
    <div style="background:var(--t-primary-bg);border-radius:10px;padding:10px;text-align:center;"><div style="font-size:9px;color:var(--t-text-muted);text-transform:uppercase;">Students</div><div style="font-size:24px;font-weight:700;color:var(--t-text);">{analytics_data['total_students']}</div></div>
  </div>
  <h2>Standards Mastery</h2>
  {standards_html}
  <div style="margin-top:16px;"><h2>Insights</h2>{insights_html}</div>
  <div class="footer">Generated by Lulia AI Analytics</div>
</div></body></html>"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_analytics(class_id: str) -> dict:
    """Run the full analytics pipeline for a class."""
    log.info(f"[Analytics] Running for class {class_id}")

    data = aggregate_class_data(class_id)
    insights = generate_insights(data)

    # Store snapshot
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO analytics_snapshots
           (snapshot_id, class_id, snapshot_date, period_type, aggregated_data, insights)
           VALUES (%s, %s, %s, 'daily', %s, %s)""",
        (str(uuid4()), class_id, date.today(), Json(data), Json(insights)),
    )
    conn.commit()
    cur.close()
    conn.close()

    data["insights"] = insights
    return data


def get_planner_analytics(class_id: str) -> dict:
    """
    Get analytics data formatted for the Planner feedback loop.
    Returns struggling_standards, mastered_standards, and recommendations.
    """
    data = aggregate_class_data(class_id)
    insights = generate_insights(data)

    return {
        "class_average": data["class_average"],
        "struggling_standards": [s["standard_code"] for s in data.get("struggling_standards", [])],
        "mastered_standards": [s["standard_code"] for s in data.get("mastered_standards", [])],
        "struggling_student_count": len(data.get("struggling_students", [])),
        "recommendations": [i.get("action", "") for i in insights if i.get("priority") == "high"],
    }
