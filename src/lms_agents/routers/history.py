"""Generation History routes — query and stats."""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Query
from src.lms_agents.tools.generation_history import query_history, get_history_stats
from src.lms_agents.tools.auth import require_teacher

router = APIRouter(prefix="/history", tags=["Generation History"])


@router.get("")
async def get_history(
    standard_codes: str = Query(None, description="Comma-separated standard codes"),
    freshness_months: int = Query(6),
    teacher_id: str = Depends(require_teacher),
):
    """Query generation history for a teacher + standards."""
    codes = [c.strip() for c in standard_codes.split(",")] if standard_codes else []
    results = query_history(teacher_id, codes, freshness_months)
    return {"history": results, "count": len(results)}


@router.get("/stats")
async def history_stats(
    teacher_id: str = Depends(require_teacher),
):
    """Get generation history stats for a teacher."""
    stats = get_history_stats(teacher_id)
    return stats
