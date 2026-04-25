"""Knowledge Base routes — search and list sources."""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Query
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import RealDictCursor

from src.lms_agents.tools.rag_search import search_kb

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/search")
async def search_knowledge_base(
    query: str = Query(..., description="Search query text"),
    teacher_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20),
):
    """
    Semantic search over the Knowledge Base using pgvector.
    Embeds the query via Bedrock, returns ranked results by cosine similarity.
    When class_id is provided, scopes results to that class + teacher-wide content.
    """
    results = search_kb(
        query=query,
        teacher_id=teacher_id,
        class_id=class_id,
        subject=subject,
        grade=grade,
        top_k=top_k,
    )
    return {"query": query, "results": results, "count": len(results)}


@router.get("/sources")
async def list_sources(
    teacher_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """List all knowledge sources with processing status. Optionally filter by class_id."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    conditions = []
    params = []
    if teacher_id:
        conditions.append("teacher_id = %s::uuid")
        params.append(teacher_id)
    if class_id:
        conditions.append("class_id = %s::uuid")
        params.append(class_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur.execute(
        f"""SELECT source_id, name, file_type, subject, grade_level, unit,
                   upload_lane, chunk_count, processing_status, uploaded_at,
                   class_id, scope
            FROM knowledge_sources
            {where}
            ORDER BY uploaded_at DESC""",
        params,
    )
    rows = cur.fetchall()
    cur.close()
    return {"sources": [dict(r) for r in rows]}
