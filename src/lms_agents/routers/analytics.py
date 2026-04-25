"""Analytics routes — class/student performance, insights, reports."""
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import RealDictCursor

from src.lms_agents.crews.analytics_crew import (
    run_analytics, aggregate_class_data, generate_insights,
    generate_class_report, get_planner_analytics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/class/{class_id}")
async def class_analytics(class_id: UUID):
    """Full class analytics dashboard data."""
    data = run_analytics(str(class_id))
    return data


@router.get("/class/{class_id}/standards")
async def standards_heatmap(class_id: UUID):
    """Standards mastery heatmap data."""
    data = aggregate_class_data(str(class_id))
    return {
        "class_id": str(class_id),
        "standards": data.get("standards", []),
        "mastered_count": data.get("mastered_count", 0),
        "needs_work_count": data.get("needs_work_count", 0),
    }


@router.get("/class/{class_id}/trends")
async def mastery_trends(class_id: UUID, conn=Depends(get_db)):
    """Mastery trend data over time."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT standard_code, date, mastery_percent
           FROM standard_mastery_history
           WHERE class_id = %s
           ORDER BY date ASC, standard_code""",
        (str(class_id),),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"trends": rows}


@router.get("/student/{student_id}")
async def student_analytics(student_id: UUID, conn=Depends(get_db)):
    """Individual student performance."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT standard_id, total_questions, correct_questions,
                  mastery_percentage, trend, last_assessed
           FROM student_mastery
           WHERE student_id = %s
           ORDER BY standard_id""",
        (str(student_id),),
    )
    mastery = [dict(r) for r in cur.fetchall()]

    total_q = sum(m["total_questions"] for m in mastery)
    correct_q = sum(m["correct_questions"] for m in mastery)
    average = round(correct_q / max(total_q, 1) * 100, 1)

    cur.close()
    return {
        "student_id": str(student_id),
        "average_mastery": average,
        "total_questions": total_q,
        "standards": mastery,
    }


@router.get("/student/{student_id}/recommendations")
async def student_recommendations(student_id: UUID, conn=Depends(get_db)):
    """AI-generated recommendations for differentiation."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM student_mastery WHERE student_id = %s ORDER BY mastery_percentage ASC",
        (str(student_id),),
    )
    mastery = [dict(r) for r in cur.fetchall()]
    cur.close()

    struggling = [m for m in mastery if m["mastery_percentage"] < 65]
    strong = [m for m in mastery if m["mastery_percentage"] >= 85]

    recommendations = []
    if struggling:
        recommendations.append({
            "type": "accommodation",
            "message": f"Student is struggling with {len(struggling)} standards",
            "action": "Consider IEP/504 accommodation for future assignments",
            "standards": [s["standard_id"] for s in struggling],
        })
    if strong:
        recommendations.append({
            "type": "enrichment",
            "message": f"Student excels at {len(strong)} standards",
            "action": "Consider gifted enrichment challenges",
            "standards": [s["standard_id"] for s in strong],
        })

    return {"student_id": str(student_id), "recommendations": recommendations}


@router.get("/struggling-students")
async def struggling_students(class_id: str = Query(...), conn=Depends(get_db)):
    """List students needing support."""
    data = aggregate_class_data(class_id)
    return {"students": data.get("struggling_students", [])}


@router.get("/struggling-standards")
async def struggling_standards(class_id: str = Query(...)):
    """List standards needing re-teaching."""
    data = aggregate_class_data(class_id)
    return {"standards": data.get("struggling_standards", [])}


@router.post("/reports/generate")
async def generate_report(
    class_id: str = Query(...),
    report_type: str = Query("class"),
):
    """Generate a printable analytics report."""
    data = aggregate_class_data(class_id)
    insights = generate_insights(data)

    if report_type == "class":
        html = generate_class_report(class_id, data, insights)
    else:
        html = generate_class_report(class_id, data, insights)

    return {"report_html": html, "class_id": class_id, "report_type": report_type}
