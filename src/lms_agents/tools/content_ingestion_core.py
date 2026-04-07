"""
Content Ingestion Core — shared chunk -> embed -> tag -> store pipeline.

All content sources (OpenStax, LibreTexts, file uploads, URLs) funnel
through ingest_sections() so the DB-write logic lives in one place.
"""
import logging
import os
from uuid import uuid4

from psycopg2.extras import Json

from src.lms_agents.tools.bedrock_embedding import embed_batch
from src.lms_agents.tools.db import get_connection
from src.lms_agents.tools.knowledge_ingestion import (
    chunk_sections,
    tag_chunks_with_standards,
)

log = logging.getLogger(__name__)

SYSTEM_TEACHER_ID = "00000000-0000-0000-0000-000000000000"


def source_exists(name: str) -> bool:
    """Check if a source with this name has already been ingested."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM knowledge_sources WHERE name = %s LIMIT 1",
            (name,),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def ingest_sections(
    sections: list[dict],
    name: str,
    teacher_id: str = SYSTEM_TEACHER_ID,
    subject: str | None = None,
    grade_level: str | None = None,
    upload_lane: str = "oer",
    file_type: str = "url",
    original_path: str = "",
) -> dict:
    """
    Universal ingestion: chunk -> embed -> tag -> store.

    Parameters
    ----------
    sections : list[dict]
        Each dict has keys {page, heading, text}.
    name : str
        Unique human-readable name for this source (used for idempotency).
    teacher_id : str
        Owner UUID. Defaults to system teacher.
    subject, grade_level : str | None
        Used for standards tagging.
    upload_lane : str
        Category label stored in knowledge_sources.
    file_type : str
        File type label stored in knowledge_sources.
    original_path : str
        Where the content came from (URL, file path, etc.).

    Returns
    -------
    dict with source_id, chunk_count, embedded_count, status.
    """
    # Idempotency check
    if source_exists(name):
        log.info(f"  Skipping (exists): {name}")
        return {"source_id": None, "chunk_count": 0, "embedded_count": 0, "status": "skipped"}

    if not sections:
        log.warning(f"  No sections for: {name}")
        return {"source_id": None, "chunk_count": 0, "embedded_count": 0, "status": "empty"}

    # 1. Chunk
    chunks = chunk_sections(sections)
    if not chunks:
        return {"source_id": None, "chunk_count": 0, "embedded_count": 0, "status": "empty"}

    log.info(f"  {name}: {len(chunks)} chunks")

    # 2. Embed
    texts = [c["content"] for c in chunks]
    embeddings = embed_batch(texts)
    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i]
    embedded_count = sum(1 for e in embeddings if e is not None)

    # 3. Tag with standards
    chunks = tag_chunks_with_standards(chunks, subject, grade_level)

    # 4. Store in database
    conn = get_connection()
    cur = conn.cursor()
    source_id = str(uuid4())

    try:
        cur.execute(
            """INSERT INTO knowledge_sources
               (source_id, teacher_id, name, file_type, original_path, subject,
                grade_level, upload_lane, chunk_count, processing_status)
               VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, 'complete')""",
            (source_id, teacher_id, name, file_type, original_path,
             subject, grade_level, upload_lane, len(chunks)),
        )

        for chunk in chunks:
            chunk_id = str(uuid4())
            embedding = chunk.get("embedding")
            embedding_str = (
                f"[{','.join(str(x) for x in embedding)}]" if embedding else None
            )
            cur.execute(
                """INSERT INTO knowledge_chunks
                   (chunk_id, source_id, chunk_number, content, embedding,
                    standards_tags, page_number, section_heading)
                   VALUES (%s, %s, %s, %s, %s::vector, %s, %s, %s)""",
                (chunk_id, source_id, chunk["chunk_number"], chunk["content"],
                 embedding_str, Json(chunk.get("standards_tags", [])),
                 chunk.get("page_number"), chunk.get("section_heading")),
            )

        conn.commit()
        log.info(f"  Stored {len(chunks)} chunks ({embedded_count} embedded) for {name}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return {
        "source_id": source_id,
        "chunk_count": len(chunks),
        "embedded_count": embedded_count,
        "status": "complete",
    }
