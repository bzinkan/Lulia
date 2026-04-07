"""
RAG Search Tool — semantic search over knowledge_chunks using pgvector.

Used by Content Agent, QA Agent, and Video Script Agent to find relevant
curriculum materials before generating content.
"""
import logging
from psycopg2.extras import RealDictCursor, Json

from src.lms_agents.tools.bedrock_embedding import embed_text
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


def search_kb(
    query: str,
    teacher_id: str | None = None,
    subject: str | None = None,
    grade: str | None = None,
    standards_ids: list[str] | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Semantic search over the knowledge base.

    1. Embeds the query via Bedrock Titan V2
    2. Searches knowledge_chunks using pgvector cosine similarity (<=>)
    3. Filters by teacher, subject, grade, standards if provided
    4. Returns ranked results with content, source, distance

    Returns empty list if embedding fails (Bedrock unavailable).
    """
    query_embedding = embed_text(query)
    if query_embedding is None:
        log.warning("Query embedding failed — returning empty results")
        return []

    embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

    conditions = ["ks.processing_status = 'complete'"]
    params: list = []

    if teacher_id:
        # Search both teacher's own content AND system-level OER content
        conditions.append("(ks.teacher_id = %s::uuid OR ks.upload_lane = 'oer_textbook')")
        params.append(teacher_id)
    if subject:
        conditions.append("ks.subject ILIKE %s")
        params.append(f"%{subject}%")
    if grade:
        conditions.append("ks.grade_level = %s")
        params.append(grade)
    if standards_ids:
        # Match chunks where any standards_tag overlaps with the query
        conditions.append("kc.standards_tags ?| %s")
        params.append(standards_ids)

    where = " AND ".join(conditions)

    # Build params in SQL order: SELECT embedding, WHERE filters, ORDER embedding, LIMIT
    all_params = [embedding_str] + params + [embedding_str, top_k]

    sql = f"""
        SELECT kc.chunk_id, kc.content, kc.section_heading, kc.page_number,
               kc.standards_tags, kc.chunk_number,
               ks.source_id, ks.name AS source_name, ks.file_type,
               ks.subject, ks.grade_level,
               kc.embedding <=> %s::vector AS distance
        FROM knowledge_chunks kc
        JOIN knowledge_sources ks ON kc.source_id = ks.source_id
        WHERE {where}
          AND kc.embedding IS NOT NULL
        ORDER BY kc.embedding <=> %s::vector ASC
        LIMIT %s
    """

    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, all_params)
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
    finally:
        conn.close()

    return results


def search_kb_simple(query: str, top_k: int = 5) -> list[dict]:
    """
    Simplified search — no filters, just query text and top_k.
    Useful for quick testing and the chat sidebar.
    """
    return search_kb(query=query, top_k=top_k)
