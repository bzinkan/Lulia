"""
Standards routes — three-tier query with priority ordering.

Tier 1 (Custom) > Tier 2 (State) > Tier 3 (National).
"""
import json
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
import os

log = logging.getLogger(__name__)
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


@router.get("/standards/retrieve")
async def retrieve_aligned_content(
    code: str = Query(..., description="Standard code to retrieve content for"),
    grade: str = Query(None, description="Grade level (K, 1-12) for filtering"),
    subject: str = Query(None, description="Subject filter"),
    top_k: int = Query(10, ge=1, le=50, description="Max results"),
):
    """Retrieve content chunks aligned to a specific standard."""
    from src.lms_agents.tools.standards_alignment import (
        retrieve_for_standard,
        retrieve_for_teaching_assignment,
        _grade_to_band,
    )

    try:
        if grade:
            results = retrieve_for_teaching_assignment(
                standard_codes=[code],
                grade=grade,
                subject=subject or "",
                top_k=top_k,
            )
        else:
            results = retrieve_for_standard(
                standard_code=code,
                grade_band=None,
                subject=subject,
                top_k=top_k,
            )

        # Serialize UUIDs and other non-JSON types
        for r in results:
            for k, v in r.items():
                if hasattr(v, "hex"):  # UUID
                    r[k] = str(v)

        return {"results": results, "count": len(results), "code": code}
    except Exception as e:
        log.warning(f"[Standards] Retrieval failed: {e}")
        return {"results": [], "count": 0, "code": code, "error": str(e)}


class SuggestStandardsRequest(BaseModel):
    description: str = ""
    subject: str = "Mathematics"
    grade: str = "4"
    worksheet_content: list[dict] = []


@router.post("/standards/suggest")
async def suggest_standards(req: SuggestStandardsRequest, conn=Depends(get_db)):
    """
    AI-powered standards suggestion. Accepts either:
    - A text description of what the teacher is teaching
    - The worksheet components (we extract question/instruction text)
    Uses Claude Haiku to identify likely standard codes, then matches against the DB.
    """
    # Build context from worksheet content and/or description
    content_texts = []
    if req.description:
        content_texts.append(f"Teacher description: {req.description}")
    for comp in req.worksheet_content:
        for key in ("question", "text", "html", "sentence", "statement", "problem"):
            val = comp.get("config", comp).get(key, "")
            if val and len(val) > 3:
                content_texts.append(val)

    if not content_texts:
        return {"standards": [], "reasoning": "No content provided to analyze."}

    combined = "\n".join(content_texts[:20])  # Cap to avoid huge prompts

    # Ask Claude to identify standards
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"standards": [], "reasoning": "AI unavailable — no API key configured."}

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are an expert curriculum standards specialist. Analyze the following worksheet content and identify the most relevant educational standards.

Subject: {req.subject}
Grade Level: {req.grade}

Worksheet content:
{combined}

Return a JSON object with:
- "codes": array of 3-8 standard codes that best match (e.g. ["4.NF.1", "4.NF.2", "CCSS.MATH.CONTENT.4.NF.A.1"])
- "search_terms": array of 2-4 keyword phrases to search a standards database (e.g. ["equivalent fractions", "number line fractions"])
- "reasoning": one sentence explaining why these standards apply

Return ONLY the JSON object."""

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # Parse JSON from response
        import re
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        ai_result = json.loads(text)
    except Exception as e:
        log.warning(f"[Standards] AI suggestion failed: {e}")
        return {"standards": [], "reasoning": f"AI analysis failed: {e}"}

    codes = ai_result.get("codes", [])
    search_terms = ai_result.get("search_terms", [])
    reasoning = ai_result.get("reasoning", "")

    # Search DB for matching standards
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    matched = []

    # First: try exact code matches
    for code in codes:
        cur.execute(
            """SELECT s.standard_id, s.code, s.description, s.grade_level, s.subject,
                      s.domain, f.name AS framework_name, f.tier, f.priority
               FROM standards s
               JOIN standards_frameworks f ON s.framework_id = f.framework_id
               WHERE f.is_active = true AND s.code ILIKE %s
               ORDER BY f.priority ASC LIMIT 3""",
            (f"%{code}%",),
        )
        matched.extend([dict(r) for r in cur.fetchall()])

    # Then: keyword search if we need more results
    if len(matched) < 3:
        for term in search_terms:
            cur.execute(
                """SELECT s.standard_id, s.code, s.description, s.grade_level, s.subject,
                          s.domain, f.name AS framework_name, f.tier, f.priority
                   FROM standards s
                   JOIN standards_frameworks f ON s.framework_id = f.framework_id
                   WHERE f.is_active = true
                     AND s.description ILIKE %s
                     AND s.grade_level = %s
                   ORDER BY f.priority ASC LIMIT 5""",
                (f"%{term}%", req.grade),
            )
            matched.extend([dict(r) for r in cur.fetchall()])

    cur.close()

    # Deduplicate by standard_id
    seen = set()
    unique = []
    for s in matched:
        sid = s["standard_id"]
        if sid not in seen:
            seen.add(sid)
            unique.append(s)

    return {
        "standards": unique[:10],
        "reasoning": reasoning,
        "ai_codes": codes,
    }
