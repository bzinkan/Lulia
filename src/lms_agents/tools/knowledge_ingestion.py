"""
Knowledge Ingestion Pipeline — processes uploaded files into chunked,
embedded, standards-tagged entries in knowledge_chunks.

Supports: PDF, DOCX, TXT, URL
"""
import json
import logging
import os
import re

import httpx

log = logging.getLogger(__name__)

CHUNK_TARGET_WORDS = 400
CHUNK_MAX_WORDS = 600


# ---------------------------------------------------------------------------
# Text extraction by file type
# ---------------------------------------------------------------------------

def extract_pdf(file_path: str) -> list[dict]:
    """Extract text from PDF using PyMuPDF. Returns list of {page, heading, text}."""
    import fitz  # PyMuPDF

    doc = fitz.open(file_path)
    sections = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        page_text = ""
        current_heading = None

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text = "".join(span["text"] for span in line["spans"]).strip()
                if not line_text:
                    continue
                # Detect headings by font size (>= 14pt) or bold
                is_heading = any(
                    span["size"] >= 14 or "bold" in span["font"].lower()
                    for span in line["spans"]
                )
                if is_heading and len(line_text) < 200:
                    if page_text.strip():
                        sections.append({
                            "page": page_num + 1,
                            "heading": current_heading,
                            "text": page_text.strip(),
                        })
                        page_text = ""
                    current_heading = line_text
                else:
                    page_text += line_text + " "

        if page_text.strip():
            sections.append({
                "page": page_num + 1,
                "heading": current_heading,
                "text": page_text.strip(),
            })
    doc.close()
    return sections


def extract_docx(file_path: str) -> list[dict]:
    """Extract text from DOCX using python-docx. Returns list of {heading, text}."""
    from docx import Document

    doc = Document(file_path)
    sections = []
    current_heading = None
    current_text = ""

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style.name.startswith("Heading"):
            if current_text:
                sections.append({
                    "page": None,
                    "heading": current_heading,
                    "text": current_text.strip(),
                })
                current_text = ""
            current_heading = text
        else:
            current_text += text + " "

    if current_text.strip():
        sections.append({
            "page": None,
            "heading": current_heading,
            "text": current_text.strip(),
        })
    return sections


def extract_text(file_path: str) -> list[dict]:
    """Extract text from a plain text file, splitting on blank lines."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    paragraphs = re.split(r"\n\s*\n", content)
    sections = []
    for para in paragraphs:
        text = para.strip()
        if text:
            sections.append({"page": None, "heading": None, "text": text})
    return sections


def extract_url(url: str) -> list[dict]:
    """Fetch URL and extract main content using BeautifulSoup."""
    from bs4 import BeautifulSoup

    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove scripts, styles, nav
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # Try to find main content
    main = soup.find("main") or soup.find("article") or soup.find("body")
    if not main:
        return []

    sections = []
    current_heading = None
    current_text = ""

    for element in main.descendants:
        if element.name in ("h1", "h2", "h3", "h4"):
            if current_text.strip():
                sections.append({
                    "page": None,
                    "heading": current_heading,
                    "text": current_text.strip(),
                })
                current_text = ""
            current_heading = element.get_text(strip=True)
        elif element.name in ("p", "li", "td"):
            text = element.get_text(strip=True)
            if text:
                current_text += text + " "

    if current_text.strip():
        sections.append({
            "page": None,
            "heading": current_heading,
            "text": current_text.strip(),
        })
    return sections


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_sections(sections: list[dict]) -> list[dict]:
    """
    Split sections into chunks of ~CHUNK_TARGET_WORDS words.
    Preserves page numbers and headings.
    """
    chunks = []
    chunk_num = 0

    for section in sections:
        words = section["text"].split()
        if len(words) <= CHUNK_MAX_WORDS:
            chunk_num += 1
            chunks.append({
                "chunk_number": chunk_num,
                "content": section["text"],
                "page_number": section.get("page"),
                "section_heading": section.get("heading"),
            })
        else:
            # Split into multiple chunks at sentence boundaries
            sentences = re.split(r"(?<=[.!?])\s+", section["text"])
            current_chunk = ""
            for sentence in sentences:
                if len((current_chunk + " " + sentence).split()) > CHUNK_TARGET_WORDS and current_chunk:
                    chunk_num += 1
                    chunks.append({
                        "chunk_number": chunk_num,
                        "content": current_chunk.strip(),
                        "page_number": section.get("page"),
                        "section_heading": section.get("heading"),
                    })
                    current_chunk = sentence
                else:
                    current_chunk += " " + sentence
            if current_chunk.strip():
                chunk_num += 1
                chunks.append({
                    "chunk_number": chunk_num,
                    "content": current_chunk.strip(),
                    "page_number": section.get("page"),
                    "section_heading": section.get("heading"),
                })
    return chunks


# ---------------------------------------------------------------------------
# Standards auto-tagging via Claude Haiku
# ---------------------------------------------------------------------------

def tag_chunks_with_standards(
    chunks: list[dict], subject: str | None, grade: str | None
) -> list[dict]:
    """
    Use Claude Haiku to classify which standards each chunk relates to.
    Falls back gracefully if API key not set or rate limited.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping standards tagging")
        for c in chunks:
            c["standards_tags"] = []
        return chunks

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        log.warning(f"Failed to init Anthropic client: {e}")
        for c in chunks:
            c["standards_tags"] = []
        return chunks

    # Batch chunks into groups to reduce API calls
    batch_size = 5
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        chunk_texts = "\n---\n".join(
            f"Chunk {c['chunk_number']}: {c['content'][:500]}" for c in batch
        )
        prompt = (
            f"You are a standards alignment expert. For each chunk of educational content below, "
            f"identify which educational standard codes it most closely relates to. "
            f"Subject context: {subject or 'unknown'}. Grade context: {grade or 'unknown'}.\n\n"
            f"{chunk_texts}\n\n"
            f"Respond ONLY with a JSON array of arrays, one per chunk, containing standard code "
            f"strings (e.g. [\"4.NF.1\", \"4.NF.2\"]). If no standards match, use an empty array. "
            f"Example for 3 chunks: [[\"4.NF.1\"], [\"4.OA.3\", \"4.OA.4\"], []]"
        )

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            # Extract JSON array from response
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                tags_list = json.loads(match.group())
                for j, chunk in enumerate(batch):
                    chunk["standards_tags"] = tags_list[j] if j < len(tags_list) else []
            else:
                for c in batch:
                    c["standards_tags"] = []
        except Exception as e:
            log.warning(f"Standards tagging failed for batch: {e}")
            for c in batch:
                c["standards_tags"] = []

    return chunks


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------

def ingest_file(
    file_path: str,
    file_type: str,
    name: str,
    teacher_id: str,
    upload_lane: str = "materials",
    subject: str | None = None,
    grade_level: str | None = None,
    unit: str | None = None,
) -> dict:
    """
    Full ingestion pipeline: extract -> chunk -> embed -> tag -> store.
    Returns dict with source_id, chunk_count, embedded_count, status.

    Delegates the chunk/embed/tag/store to content_ingestion_core.ingest_sections().
    """
    from src.lms_agents.tools.content_ingestion_core import ingest_sections

    log.info(f"Ingesting {name} ({file_type})")

    # 1. Extract text sections
    if file_type == "pdf":
        sections = extract_pdf(file_path)
    elif file_type in ("docx", "doc"):
        sections = extract_docx(file_path)
    elif file_type in ("txt", "text", "md"):
        sections = extract_text(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    if not sections:
        log.warning(f"No content extracted from {name}")
        return {"source_id": None, "chunk_count": 0, "status": "empty"}

    log.info(f"  Extracted {len(sections)} sections")

    return ingest_sections(
        sections=sections,
        name=name,
        teacher_id=teacher_id,
        subject=subject,
        grade_level=grade_level,
        upload_lane=upload_lane,
        file_type=file_type,
        original_path=file_path,
    )


def ingest_url(
    url: str,
    name: str,
    teacher_id: str,
    subject: str | None = None,
    grade_level: str | None = None,
) -> dict:
    """Ingest content from a URL. Delegates to shared core pipeline."""
    from src.lms_agents.tools.content_ingestion_core import ingest_sections

    log.info(f"Ingesting URL: {url}")

    sections = extract_url(url)
    if not sections:
        return {"source_id": None, "chunk_count": 0, "status": "empty"}

    return ingest_sections(
        sections=sections,
        name=name,
        teacher_id=teacher_id,
        subject=subject,
        grade_level=grade_level,
        upload_lane="materials",
        file_type="url",
        original_path=url,
    )
