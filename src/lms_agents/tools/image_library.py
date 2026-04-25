"""
Teacher image library lookup — find images relevant to a given topic so the
artifact-mode interactive generator can embed them in produced activities.

Strategy (simple, good enough for a small library):
  1. Tokenize the topic into lowercase keywords (drop stopwords, punctuation).
  2. For each token, look for tag overlap (exact tag match via GIN index).
  3. Also match against the free-text `description` via trigram similarity.
  4. Union results, score by number of tag hits + description similarity,
     return top N.

No vector search required for library sizes up to a few thousand images.
"""
import logging
import re
from typing import List

log = logging.getLogger(__name__)

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "about", "from", "as", "by", "is", "are", "was", "were", "be",
    "their", "its", "this", "that", "these", "those",
    "how", "what", "when", "where", "why", "which", "who",
    "functions", "function", "parts", "part", "introduction",
}


def _tokenize(topic: str) -> List[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]*", topic.lower())
    out = []
    seen = set()
    for w in words:
        w = w.strip("-")
        if not w or w in _STOPWORDS or len(w) <= 2:
            continue
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def find_relevant_images(
    topic: str,
    teacher_id: str | None = None,
    limit: int = 3,
    min_score: float = 0.1,
    include_generated: bool = False,
) -> List[dict]:
    """
    Return up to `limit` images matching the topic.

    Each item: {image_id, storage_url, thumbnail_url, description, tags, score}
    Only rows with a caption (`description IS NOT NULL`) are considered —
    images without captions aren't searchable.

    By default, `source='generated'` images are EXCLUDED because historical
    AI image generation produced plant cells with hallucinated labels like
    "Theck creasiolis". Teacher-UPLOADED images are trustworthy. Set
    include_generated=True to search all sources.
    """
    from psycopg2.extras import RealDictCursor
    from src.lms_agents.tools.db import get_connection

    tokens = _tokenize(topic or "")
    if not tokens:
        return []

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Scored query:
    #   - tag_hits: count of tokens that appear as exact tags
    #   - desc_score: similarity(description, topic) — 0..1 via pg_trgm
    # Combined score = tag_hits + desc_score. Require description present.
    params: list = [tokens, topic]
    where_clauses = ["description IS NOT NULL"]
    if not include_generated:
        where_clauses.append("(source IS NULL OR source <> 'generated')")
    if teacher_id:
        where_clauses.append("teacher_id = %s::uuid")
        params.append(teacher_id)

    sql = f"""
        SELECT image_id, storage_url, thumbnail_url, description, tags, source,
               (
                 COALESCE(array_length(
                   ARRAY(SELECT UNNEST(tags) INTERSECT SELECT UNNEST(%s::text[])), 1
                 ), 0)
               ) AS tag_hits,
               GREATEST(similarity(description, %s), 0) AS desc_score
        FROM teacher_images
        WHERE {" AND ".join(where_clauses)}
        ORDER BY (
          COALESCE(array_length(
            ARRAY(SELECT UNNEST(tags) INTERSECT SELECT UNNEST(%s::text[])), 1
          ), 0) + similarity(description, %s)
        ) DESC
        LIMIT %s
    """
    params.extend([tokens, topic, limit])
    cur.execute(sql, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    # Filter by combined score threshold
    out = []
    for r in rows:
        score = float(r.get("tag_hits") or 0) + float(r.get("desc_score") or 0)
        if score < min_score:
            continue
        r["score"] = round(score, 3)
        # Serialize UUIDs so the caller can JSON-encode cleanly
        r["image_id"] = str(r["image_id"])
        out.append(r)
    log.info(f"[ImageLibrary] topic='{topic[:40]}' tokens={tokens} -> {len(out)} matches (include_generated={include_generated})")
    return out


def find_wikimedia_image(topic: str, limit: int = 2) -> List[dict]:
    """
    Fallback: search Wikimedia Commons for textbook-accurate educational
    diagrams. Used when the teacher's library has no uploaded match.
    Returns the same shape as find_relevant_images.

    Wikimedia is CDN-hosted and CORS-friendly — browsers can load URLs
    directly via <img src>, no rehosting needed.
    """
    import httpx
    import re as _re
    tokens = _tokenize(topic or "")
    if not tokens:
        return []
    # Use the 2-3 most specific tokens for Wikimedia — the full topic phrase
    # ("plant cell organelles and their functions") returns irrelevant matches.
    # The tokenizer already filters stopwords like 'and', 'their', 'functions'.
    query = " ".join(tokens[:3])
    # Wikimedia blocks unidentified clients with 403 — the UA must identify
    # the app + a contact per their API etiquette policy.
    headers = {
        "User-Agent": "LuliaLMS/1.0 (https://lulia.app; contact@lulia.app)",
        "Accept": "application/json",
    }
    try:
        resp = httpx.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 6,
                "gsrlimit": max(limit, 6),
                "prop": "imageinfo",
                "iiprop": "url|mime|extmetadata",
                "iiurlwidth": 800,
                "format": "json",
            },
            headers=headers,
            timeout=8,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
    except Exception as e:
        log.warning(f"[ImageLibrary] Wikimedia search failed: {e}")
        return []

    out = []
    for pid, page in pages.items():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if not mime.startswith("image/"):
            continue
        url = info.get("url") or info.get("thumburl")
        if not url:
            continue
        # Prefer PNG/JPEG over SVG (SVG can be fragile in <img>)
        title = page.get("title", "File:unknown").replace("File:", "")
        meta = info.get("extmetadata", {})
        artist = _re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "Wikimedia")).strip()[:60]
        desc = _re.sub(r"<[^>]+>", "", meta.get("ImageDescription", {}).get("value", title)).strip()[:250]
        out.append({
            "image_id": f"wiki_{pid}",
            "storage_url": url,
            "thumbnail_url": info.get("thumburl", url),
            "description": desc or title,
            "tags": tokens,
            "score": 1.0,
            "source": "wikimedia",
            "attribution": f"{artist} — Wikimedia Commons",
        })
        if len(out) >= limit:
            break
    log.info(f"[ImageLibrary] Wikimedia fallback '{topic[:40]}' -> {len(out)} matches")
    return out


def find_best_images(
    topic: str,
    teacher_id: str | None = None,
    limit: int = 3,
) -> List[dict]:
    """
    Preferred lookup used by the artifact generator.

    Cascade:
      1. Teacher-uploaded library (excluding AI-generated junk)
      2. Wikimedia Commons fallback (real textbook diagrams)
    """
    uploads = find_relevant_images(topic, teacher_id=teacher_id, limit=limit, include_generated=False)
    if uploads:
        return uploads
    return find_wikimedia_image(topic, limit=limit)
