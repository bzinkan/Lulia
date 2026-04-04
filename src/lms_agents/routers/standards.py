"""
Standards routes — three-tier query with priority ordering.

Tier 1 (Custom) > Tier 2 (State) > Tier 3 (National).
"""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query
import psycopg2
import psycopg2.extras
import os

router = APIRouter(tags=["Standards"])


def get_db():
    """Yield a database connection."""
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )
    try:
        yield conn
    finally:
        conn.close()


@router.get("/standards/frameworks")
async def list_frameworks(
    tier: Optional[str] = Query(None, description="Filter by tier: custom, state, national"),
    conn=Depends(get_db),
):
    """List all standards frameworks, ordered by tier priority."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if tier:
        cur.execute(
            """SELECT framework_id, name, tier, state_code, authority,
                      subjects_covered, grade_range, is_active, priority
               FROM standards_frameworks
               WHERE tier = %s AND is_active = true
               ORDER BY priority ASC, name ASC""",
            (tier,),
        )
    else:
        cur.execute(
            """SELECT framework_id, name, tier, state_code, authority,
                      subjects_covered, grade_range, is_active, priority
               FROM standards_frameworks
               WHERE is_active = true
               ORDER BY priority ASC, name ASC""",
        )
    rows = cur.fetchall()
    cur.close()
    return {"frameworks": [dict(r) for r in rows]}


@router.get("/standards")
async def query_standards(
    subject: Optional[str] = Query(None, description="Filter by subject (Math, ELA, Science)"),
    grade: Optional[str] = Query(None, description="Filter by grade level (K, 1-12)"),
    framework_id: Optional[str] = Query(None, description="Filter by specific framework"),
    state_code: Optional[str] = Query(None, description="Filter by state code (OH, CA, etc.)"),
    code: Optional[str] = Query(None, description="Search by standard code (partial match)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    """
    Query standards with three-tier priority ordering.

    Results are ordered by framework priority (1=custom, 2=state, 3=national)
    so that the highest-priority standards appear first.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    conditions = ["f.is_active = true"]
    params: list = []

    if subject:
        conditions.append("s.subject ILIKE %s")
        params.append(f"%{subject}%")
    if grade:
        conditions.append("s.grade_level = %s")
        params.append(grade)
    if framework_id:
        conditions.append("s.framework_id = %s::uuid")
        params.append(framework_id)
    if state_code:
        conditions.append("f.state_code = %s")
        params.append(state_code.upper())
    if code:
        conditions.append("s.code ILIKE %s")
        params.append(f"%{code}%")

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    cur.execute(
        f"""SELECT s.standard_id, s.code, s.description, s.grade_level,
                   s.subject, s.domain, s.cluster, s.cognitive_level,
                   f.framework_id, f.name AS framework_name,
                   f.tier, f.state_code, f.priority
            FROM standards s
            JOIN standards_frameworks f ON s.framework_id = f.framework_id
            WHERE {where}
            ORDER BY f.priority ASC, s.code ASC
            LIMIT %s OFFSET %s""",
        params,
    )
    rows = cur.fetchall()

    # Get total count for pagination
    cur.execute(
        f"""SELECT COUNT(*)
            FROM standards s
            JOIN standards_frameworks f ON s.framework_id = f.framework_id
            WHERE {where}""",
        params[:-2],  # exclude limit/offset
    )
    total = cur.fetchone()["count"]
    cur.close()

    return {
        "standards": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/standards/states")
async def list_states(conn=Depends(get_db)):
    """List all states that have standards loaded — for the settings dropdown."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT DISTINCT state_code, name, framework_id
           FROM standards_frameworks
           WHERE tier = 'state' AND is_active = true AND state_code IS NOT NULL
           ORDER BY state_code ASC""",
    )
    rows = cur.fetchall()
    cur.close()
    return {"states": [dict(r) for r in rows]}
