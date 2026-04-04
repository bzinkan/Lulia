"""Knowledge Base routes — search and list sources."""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Query
import psycopg2
from psycopg2.extras import RealDictCursor

from src.lms_agents.tools.rag_search import search_kb

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


def get_db():
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


@router.get("/search")
async def search_knowledge_base(
    query: str = Query(..., description="Search query text"),
    teacher_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20),
):
    """
    Semantic search over the Knowledge Base using pgvector.
    Embeds the query via Bedrock, returns ranked results by cosine similarity.
    """
    results = search_kb(
        query=query,
        teacher_id=teacher_id,
        subject=subject,
        grade=grade,
        top_k=top_k,
    )
    return {"query": query, "results": results, "count": len(results)}


@router.get("/sources")
async def list_sources(
    teacher_id: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """List all knowledge sources with processing status."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if teacher_id:
        cur.execute(
            """SELECT source_id, name, file_type, subject, grade_level, unit,
                      upload_lane, chunk_count, processing_status, uploaded_at
               FROM knowledge_sources
               WHERE teacher_id = %s::uuid
               ORDER BY uploaded_at DESC""",
            (teacher_id,),
        )
    else:
        cur.execute(
            """SELECT source_id, name, file_type, subject, grade_level, unit,
                      upload_lane, chunk_count, processing_status, uploaded_at
               FROM knowledge_sources
               ORDER BY uploaded_at DESC""",
        )
    rows = cur.fetchall()
    cur.close()
    return {"sources": [dict(r) for r in rows]}
