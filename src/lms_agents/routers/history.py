"""Generation History routes — query and stats."""
import os
from typing import Optional

from fastapi import APIRouter, Query
from src.lms_agents.tools.generation_history import query_history, get_history_stats

router = APIRouter(prefix="/history", tags=["Generation History"])


@router.get("")
async def get_history(
    teacher_id: str = Query(...),
    standard_codes: str = Query(None, description="Comma-separated standard codes"),
    freshness_months: int = Query(6),
):
    """Query generation history for a teacher + standards."""
    codes = [c.strip() for c in standard_codes.split(",")] if standard_codes else []
    results = query_history(teacher_id, codes, freshness_months)
    return {"history": results, "count": len(results)}


@router.get("/stats")
async def history_stats(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
):
    """Get generation history stats for a teacher."""
    stats = get_history_stats(teacher_id)
    return stats
