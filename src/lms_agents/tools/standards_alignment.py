"""
Standards Alignment Agent — deterministic, grade-appropriate content delivery.

Two-step alignment: dense retrieval via pgvector embeddings, then Claude Haiku
judgment for precision. Stores alignment_scores JSONB on knowledge_chunks for
fast retrieval by lesson planning agents.
"""
import json
import logging
import os
import re

from psycopg2.extras import Json

from src.lms_agents.tools.bedrock_embedding import embed_text, embed_batch
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema migration — safe to call repeatedly
# ---------------------------------------------------------------------------

def ensure_standards_schema():
    """Add alignment columns if they don't exist. Idempotent."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            ALTER TABLE standards
                ADD COLUMN IF NOT EXISTS embedding VECTOR(1024);
        """)
        cur.execute("""
            ALTER TABLE knowledge_chunks
                ADD COLUMN IF NOT EXISTS reading_level REAL;
        """)
        cur.execute("""
            ALTER TABLE knowledge_chunks
                ADD COLUMN IF NOT EXISTS grade_bands TEXT[] DEFAULT '{}';
        """)
        cur.execute("""
            ALTER TABLE knowledge_chunks
                ADD COLUMN IF NOT EXISTS alignment_scores JSONB DEFAULT '[]';
        """)
        conn.commit()
        log.info("Standards alignment schema verified")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Step 1: Embed all 62K+ standards
# ---------------------------------------------------------------------------

def embed_all_standards(batch_size=50):
    """
    Embed all standards that don't have an embedding yet.

    Constructs embed text as: "{code}: {description} (Grade {grade_level}, {subject}, {domain})"
    Idempotent — skips already-embedded standards.

    Returns count of newly embedded standards.
    """
    ensure_standards_schema()

    conn = get_connection()
    cur = conn.cursor()
    total_embedded = 0

    try:
        # Count total unembedded
        cur.execute("SELECT COUNT(*) FROM standards WHERE embedding IS NULL")
        remaining = cur.fetchone()[0]
        log.info(f"Standards to embed: {remaining}")

        if remaining == 0:
            return 0

        while True:
            cur.execute(
                """SELECT standard_id, code, description, grade_level, subject, domain
                   FROM standards
                   WHERE embedding IS NULL
                   LIMIT %s""",
                (batch_size,),
            )
            rows = cur.fetchall()
            if not rows:
                break

            # Build embed texts
            texts = []
            for row in rows:
                sid, code, desc, grade, subj, domain = row
                text = f"{code}: {desc} (Grade {grade}, {subj}, {domain})"
                texts.append(text)

            # Embed batch
            embeddings = embed_batch(texts)

            # Update each row
            for i, row in enumerate(rows):
                emb = embeddings[i]
                if emb is not None:
                    embedding_str = f"[{','.join(str(x) for x in emb)}]"
                    cur.execute(
                        "UPDATE standards SET embedding = %s::vector WHERE standard_id = %s",
                        (embedding_str, row[0]),
                    )
                    total_embedded += 1

            conn.commit()

            if total_embedded % 500 < batch_size:
                log.info(f"  Embedded {total_embedded}/{remaining} standards")

        log.info(f"Finished embedding {total_embedded} standards")
        return total_embedded

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Step 2: Align individual chunks
# ---------------------------------------------------------------------------

def _call_haiku(prompt: str) -> dict | None:
    """Call Claude Haiku and parse JSON response. Returns None on failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping alignment")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)
    except Exception as e:
        log.warning(f"Haiku alignment call failed: {e}")
        return None


def align_chunk(chunk_id, chunk_content, chunk_embedding, subject_hint=None, grade_hint=None):
    """
    Align a single knowledge chunk to standards. Two-step process:
    1. Dense retrieval of top-20 candidate standards via pgvector
    2. Claude Haiku judgment for precision alignment + reading level

    Updates the chunk row with alignment_scores, reading_level, grade_bands,
    and standards_tags (backwards compat).
    """
    ensure_standards_schema()

    conn = get_connection()
    cur = conn.cursor()

    try:
        # --- Step 1: Dense retrieval ---
        if chunk_embedding is None:
            log.warning(f"Chunk {chunk_id} has no embedding — skipping alignment")
            return

        embedding_str = f"[{','.join(str(x) for x in chunk_embedding)}]"

        query = """
            SELECT s.standard_id, s.code, s.description, s.grade_level, s.subject,
                   s.domain, f.tier, f.priority,
                   s.embedding <=> %s::vector AS distance
            FROM standards s
            JOIN standards_frameworks f ON s.framework_id = f.framework_id
            WHERE f.is_active = true
              AND s.embedding IS NOT NULL
        """
        params = [embedding_str]

        if subject_hint:
            query += " AND s.subject ILIKE %s"
            params.append(f"%{subject_hint}%")

        query += " ORDER BY s.embedding <=> %s::vector ASC LIMIT 20"
        params.append(embedding_str)

        cur.execute(query, params)
        candidates = cur.fetchall()

        if not candidates:
            log.info(f"No candidate standards found for chunk {chunk_id}")
            return

        # --- Step 2: Claude Haiku judgment ---
        candidate_lines = []
        for row in candidates:
            sid, code, desc, grade, subj, domain, tier, priority, dist = row
            candidate_lines.append(f"- {code}: {desc} (Grade {grade}, {subj})")

        candidates_text = "\n".join(candidate_lines)

        prompt = f"""You are an expert curriculum standards alignment specialist.

Given this educational content chunk and a list of candidate standards, determine which standards this content teaches or supports.

Content chunk:
{chunk_content[:1500]}

Candidate standards:
{candidates_text}

Also determine:
1. The reading level of this content (Flesch-Kincaid grade level, numeric)
2. The appropriate grade bands (array from: "K-2", "3-5", "6-8", "9-12", "college")

Return ONLY a JSON object:
{{
  "alignments": [
    {{"code": "4.NF.1", "strength": "strong"}},
    {{"code": "4.NF.2", "strength": "partial"}}
  ],
  "reading_level": 4.2,
  "grade_bands": ["3-5"]
}}

Rules:
- "strong" = this content directly teaches or assesses this standard
- "partial" = this content supports or builds toward this standard
- Only include standards with strong or partial alignment (omit "none")
- Be conservative — only mark "strong" if the content clearly and directly addresses the standard
- reading_level should be a numeric Flesch-Kincaid grade estimate
- grade_bands should reflect the vocabulary and cognitive complexity, not just the topic"""

        result = _call_haiku(prompt)
        if result is None:
            return

        alignments = result.get("alignments", [])
        reading_level = result.get("reading_level")
        grade_bands = result.get("grade_bands", [])

        # --- Step 3: Validate and store ---
        # Look up standard_ids for each aligned code
        alignment_scores = []
        standards_tags = []  # backwards compat

        for alignment in alignments:
            code = alignment.get("code")
            strength = alignment.get("strength", "partial")
            if not code:
                continue

            cur.execute(
                """SELECT s.standard_id, f.tier
                   FROM standards s
                   JOIN standards_frameworks f ON s.framework_id = f.framework_id
                   WHERE s.code = %s AND f.is_active = true
                   LIMIT 1""",
                (code,),
            )
            row = cur.fetchone()
            if row:
                standard_id, framework_tier = row
                alignment_scores.append({
                    "standard_id": str(standard_id),
                    "code": code,
                    "strength": strength,
                    "framework_tier": framework_tier,
                })
                standards_tags.append(code)

        # Update the chunk
        cur.execute(
            """UPDATE knowledge_chunks
               SET alignment_scores = %s,
                   reading_level = %s,
                   grade_bands = %s,
                   standards_tags = %s
               WHERE chunk_id = %s""",
            (
                Json(alignment_scores),
                reading_level,
                grade_bands if grade_bands else [],
                Json(standards_tags),
                chunk_id,
            ),
        )
        conn.commit()

        aligned_count = len(alignment_scores)
        log.debug(
            f"Chunk {chunk_id}: {aligned_count} alignments, "
            f"reading_level={reading_level}, grade_bands={grade_bands}"
        )

    except Exception as e:
        conn.rollback()
        log.warning(f"Failed to align chunk {chunk_id}: {e}")
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Batch alignment
# ---------------------------------------------------------------------------

def align_chunks_batch(source_id=None, limit=100):
    """
    Align a batch of chunks that have no alignment_scores yet.

    Parameters
    ----------
    source_id : str, optional
        If provided, only align chunks from this source.
    limit : int
        Max chunks to process in this batch.

    Returns count of chunks aligned.
    """
    ensure_standards_schema()

    conn = get_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT chunk_id, content, embedding, source_id
            FROM knowledge_chunks
            WHERE (alignment_scores = '[]'::jsonb OR alignment_scores IS NULL)
              AND embedding IS NOT NULL
        """
        params = []

        if source_id:
            query += " AND source_id = %s"
            params.append(source_id)

        query += " LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    if not rows:
        log.info("No unaligned chunks found")
        return 0

    log.info(f"Aligning {len(rows)} chunks...")

    # Look up subject hint from source if available
    subject_hint = None
    if source_id:
        conn2 = get_connection()
        cur2 = conn2.cursor()
        try:
            cur2.execute(
                "SELECT subject FROM knowledge_sources WHERE source_id = %s",
                (source_id,),
            )
            row = cur2.fetchone()
            if row and row[0]:
                subject_hint = row[0]
        finally:
            cur2.close()
            conn2.close()

    count = 0
    for i, row in enumerate(rows):
        chunk_id, content, embedding_raw, src_id = row

        # Parse the embedding from pgvector format
        if isinstance(embedding_raw, str):
            embedding = [float(x) for x in embedding_raw.strip("[]").split(",")]
        elif isinstance(embedding_raw, (list, tuple)):
            embedding = list(embedding_raw)
        else:
            # numpy array or pgvector type
            try:
                embedding = list(embedding_raw)
            except Exception:
                log.warning(f"Cannot parse embedding for chunk {chunk_id}")
                continue

        align_chunk(chunk_id, content, embedding, subject_hint=subject_hint)
        count += 1

        if (i + 1) % 10 == 0:
            log.info(f"  Aligned {i + 1}/{len(rows)} chunks")

    log.info(f"Batch complete: {count} chunks aligned")
    return count


def align_all_unaligned(batch_size=100):
    """
    Loop align_chunks_batch() until no more unaligned chunks remain.
    Returns total count aligned.
    """
    total = 0
    iteration = 0

    while True:
        iteration += 1
        count = align_chunks_batch(limit=batch_size)
        total += count
        log.info(f"Iteration {iteration}: aligned {count} chunks (total: {total})")

        if count == 0:
            break

    log.info(f"All alignment complete: {total} chunks aligned")
    return total


# ---------------------------------------------------------------------------
# Retrieval functions — used by lesson planning agents
# ---------------------------------------------------------------------------

def _grade_to_band(grade) -> str | None:
    """Convert a numeric grade (or K) to a grade band string."""
    if grade is None:
        return None
    g = str(grade).strip().upper()
    if g in ("K", "0"):
        return "K-2"
    try:
        n = int(g)
    except ValueError:
        return None
    if n <= 2:
        return "K-2"
    elif n <= 5:
        return "3-5"
    elif n <= 8:
        return "6-8"
    elif n <= 12:
        return "9-12"
    else:
        return "college"


def retrieve_for_standard(standard_code, grade_band=None, subject=None, top_k=10):
    """
    Retrieve content chunks aligned to a specific standard code.

    Parameters
    ----------
    standard_code : str
        The standard code to search for (e.g. "5-PS1-1", "4.NF.1")
    grade_band : str, optional
        Filter by grade band (e.g. "3-5", "6-8")
    subject : str, optional
        Filter by source subject
    top_k : int
        Max results to return

    Returns list of dicts with chunk metadata.
    """
    ensure_standards_schema()

    conn = get_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT kc.chunk_id, kc.content, kc.section_heading, kc.reading_level,
                   kc.grade_bands, kc.alignment_scores,
                   ks.name AS source_name, ks.upload_lane
            FROM knowledge_chunks kc
            JOIN knowledge_sources ks ON kc.source_id = ks.source_id
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(kc.alignment_scores) AS a
                WHERE a->>'code' = %s
                AND a->>'strength' = 'strong'
            )
        """
        params = [standard_code]

        if grade_band:
            query += " AND %s = ANY(kc.grade_bands)"
            params.append(grade_band)

        if subject:
            query += " AND ks.subject ILIKE %s"
            params.append(f"%{subject}%")

        query += " ORDER BY kc.reading_level ASC NULLS LAST LIMIT %s"
        params.append(top_k)

        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        return rows

    finally:
        cur.close()
        conn.close()


def retrieve_for_teaching_assignment(standard_codes, grade, subject, top_k=10):
    """
    Higher-level retrieval for a full teaching context.

    Parameters
    ----------
    standard_codes : list[str]
        List of standard codes to find content for.
    grade : str or int
        Grade level (e.g. "5", "K")
    subject : str
        Subject filter
    top_k : int
        Max results

    Returns list of dicts with chunk metadata, ranked by alignment strength
    then reading level proximity to grade.
    """
    ensure_standards_schema()

    grade_band = _grade_to_band(grade)

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Build a query that matches ANY of the standard codes
        # Using jsonb_array_elements to check against multiple codes
        codes_json = Json(standard_codes)

        query = """
            SELECT DISTINCT ON (kc.chunk_id)
                   kc.chunk_id, kc.content, kc.section_heading, kc.reading_level,
                   kc.grade_bands, kc.alignment_scores,
                   ks.name AS source_name, ks.upload_lane,
                   a.val->>'strength' AS best_strength,
                   a.val->>'code' AS matched_code
            FROM knowledge_chunks kc
            JOIN knowledge_sources ks ON kc.source_id = ks.source_id
            CROSS JOIN LATERAL jsonb_array_elements(kc.alignment_scores) AS a(val)
            WHERE a.val->>'code' = ANY(%s)
        """
        params = [standard_codes]

        if grade_band:
            query += " AND %s = ANY(kc.grade_bands)"
            params.append(grade_band)

        if subject:
            query += " AND ks.subject ILIKE %s"
            params.append(f"%{subject}%")

        # Wrap in subquery for ordering
        try:
            grade_num = float(str(grade).replace("K", "0"))
        except ValueError:
            grade_num = 5.0  # default mid-elementary

        outer_query = f"""
            SELECT * FROM ({query}) sub
            ORDER BY
                CASE WHEN best_strength = 'strong' THEN 0 ELSE 1 END ASC,
                ABS(COALESCE(reading_level, {grade_num}) - {grade_num}) ASC
            LIMIT %s
        """
        params.append(top_k)

        cur.execute(outer_query, params)
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        return rows

    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Status / diagnostics
# ---------------------------------------------------------------------------

def alignment_status():
    """Return a dict with alignment coverage statistics."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        stats = {}

        cur.execute("SELECT COUNT(*) FROM standards")
        stats["total_standards"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM standards WHERE embedding IS NOT NULL")
        stats["embedded_standards"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM knowledge_chunks")
        stats["total_chunks"] = cur.fetchone()[0]

        # Check if alignment_scores column exists before querying it
        cur.execute("""
            SELECT COUNT(*) FROM knowledge_chunks
            WHERE alignment_scores IS NOT NULL
              AND alignment_scores != '[]'::jsonb
        """)
        stats["aligned_chunks"] = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM knowledge_chunks
            WHERE (alignment_scores IS NULL OR alignment_scores = '[]'::jsonb)
              AND embedding IS NOT NULL
        """)
        stats["unaligned_chunks"] = cur.fetchone()[0]

        return stats

    except Exception as e:
        log.warning(f"Status query failed (columns may not exist yet): {e}")
        conn.rollback()
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()
