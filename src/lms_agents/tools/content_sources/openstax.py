"""
OpenStax content source — catalog sync, repo clone, CNXML parsing.

The actual chunk/embed/store is handled by content_ingestion_core.ingest_sections().
"""
import glob
import logging
import os
import re
import subprocess

import httpx
from lxml import etree

from src.lms_agents.tools.content_ingestion_core import ingest_sections, source_exists
from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

CATALOG_URL = (
    "https://raw.githubusercontent.com/openstax/"
    "content-manager-approved-books/main/approved-book-list.json"
)

NS_CNXML = "http://cnx.rice.edu/cnxml"
NS_COLLXML = "http://cnx.rice.edu/collxml"
NS_MD = "http://cnx.rice.edu/mdml"

BOOK_SUBJECT_MAP = {
    "college-algebra-2e": ("Mathematics", "9"),
    "algebra-and-trigonometry-2e": ("Mathematics", "10"),
    "precalculus-2e": ("Mathematics", "11"),
    "college-physics-2e": ("Physics", "11"),
    "biology-2e": ("Biology", "10"),
    "chemistry-2e": ("Chemistry", "11"),
    "anatomy-and-physiology-2e": ("Biology", "11"),
    "astronomy-2e": ("Science", "11"),
    "us-history": ("Social Studies", "11"),
    "american-government-3e": ("Social Studies", "11"),
    "introduction-sociology-3e": ("Social Studies", "11"),
    "psychology-2e": ("Social Studies", "11"),
    "principles-economics-3e": ("Social Studies", "11"),
    "introductory-statistics-2e": ("Mathematics", "11"),
    "world-history-volume-1": ("Social Studies", "10"),
    "world-history-volume-2": ("Social Studies", "10"),
    "introductory-business-statistics-2e": ("Mathematics", "12"),
    "elementary-algebra-2e": ("Mathematics", "8"),
    "intermediate-algebra-2e": ("Mathematics", "9"),
    "prealgebra-2e": ("Mathematics", "7"),
}


# ---------------------------------------------------------------------------
# Subject/grade lookup
# ---------------------------------------------------------------------------

def get_subject_grade(book_slug: str) -> tuple[str, str]:
    """Return (subject, grade) for a book slug, with fallback defaults."""
    return BOOK_SUBJECT_MAP.get(book_slug, ("General", "11"))


# ---------------------------------------------------------------------------
# Catalog sync
# ---------------------------------------------------------------------------

def sync_openstax_catalog() -> dict:
    """
    Fetch the OpenStax approved-book-list and upsert into openstax_catalog.
    Returns dict with counts.
    """
    log.info("Fetching OpenStax approved book list...")
    resp = httpx.get(CATALOG_URL, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()

    approved_books = data.get("approved_books", [])
    log.info(f"  Found {len(approved_books)} approved book entries")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS openstax_catalog (
                id SERIAL PRIMARY KEY,
                repository_name TEXT NOT NULL,
                book_uuid TEXT NOT NULL,
                book_slug TEXT NOT NULL UNIQUE,
                style TEXT,
                license TEXT,
                last_synced_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()

        upserted = 0
        for entry in approved_books:
            repo_name = entry.get("repository_name", "")
            versions = entry.get("versions", [])
            if not versions:
                continue
            last_version = versions[-1]
            commit_meta = last_version.get("commit_metadata", {})
            books = commit_meta.get("books", [])
            for book in books:
                book_uuid = book.get("uuid", "")
                book_slug = book.get("slug", "")
                style = book.get("style", "")
                if not book_slug:
                    continue
                cur.execute(
                    """INSERT INTO openstax_catalog
                       (repository_name, book_uuid, book_slug, style, last_synced_at)
                       VALUES (%s, %s, %s, %s, NOW())
                       ON CONFLICT (book_slug) DO UPDATE SET
                         repository_name = EXCLUDED.repository_name,
                         book_uuid = EXCLUDED.book_uuid,
                         style = EXCLUDED.style,
                         last_synced_at = NOW()""",
                    (repo_name, book_uuid, book_slug, style),
                )
                upserted += 1

        conn.commit()
        log.info(f"  Upserted {upserted} books into openstax_catalog")
        return {"total_entries": len(approved_books), "upserted": upserted}

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Repo sync (git clone / pull)
# ---------------------------------------------------------------------------

def sync_openstax_repo(content_dir: str, repository_name: str) -> dict:
    """
    Clone or pull the OpenStax repository for a book.
    Returns dict with status and license text if found.
    """
    repo_path = os.path.join(content_dir, repository_name)

    if not os.path.isdir(repo_path):
        log.info(f"Cloning openstax/{repository_name}...")
        os.makedirs(content_dir, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth", "1",
             f"https://github.com/openstax/{repository_name}.git",
             repo_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            log.error(f"  git clone failed: {result.stderr}")
            return {"status": "error", "error": result.stderr}
        log.info(f"  Cloned to {repo_path}")
    else:
        log.info(f"Pulling updates for {repository_name}...")
        result = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True,
            cwd=repo_path,
        )
        if result.returncode != 0:
            log.warning(f"  git pull failed: {result.stderr}")
        else:
            log.info(f"  Updated: {result.stdout.strip()}")

    license_text = read_license(repo_path)
    return {"status": "ok", "repo_path": repo_path, "license": license_text}


def read_license(repo_path: str) -> str | None:
    """Read license file from a repo if present."""
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        license_path = os.path.join(repo_path, name)
        if os.path.isfile(license_path):
            with open(license_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()[:2000]
    return None


# ---------------------------------------------------------------------------
# Parse book (CNXML)
# ---------------------------------------------------------------------------

def parse_book(repo_path: str, book_slug: str) -> list[dict]:
    """
    Parse an OpenStax book from its CNXML collection and modules.
    Returns list of module dicts with extracted text.
    """
    collections_dir = os.path.join(repo_path, "collections")
    if not os.path.isdir(collections_dir):
        log.error(f"  No collections/ directory in {repo_path}")
        return []

    pattern = os.path.join(collections_dir, f"{book_slug}*.collection.xml")
    matches = glob.glob(pattern)
    if not matches:
        log.error(f"  No collection XML matching {book_slug}* in {collections_dir}")
        return []

    collection_file = matches[0]
    log.info(f"Parsing collection: {os.path.basename(collection_file)}")

    tree = etree.parse(collection_file)
    root = tree.getroot()

    nsmap = {
        "col": NS_COLLXML,
        "md": NS_MD,
    }

    modules = []
    _walk_collection(root, nsmap, repo_path, book_slug, modules,
                     chapter_num=0, chapter_title=None)

    log.info(f"  Parsed {len(modules)} modules from {book_slug}")
    return modules


def _walk_collection(
    element, nsmap, repo_path, book_slug, modules,
    chapter_num, chapter_title,
):
    """Recursively walk collection XML to extract module references."""
    import re as _re
    for child in element:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""

        if tag == "subcollection":
            title_el = child.find("md:title", nsmap)
            if title_el is None:
                title_el = child.find("col:title", nsmap)
            sub_title = title_el.text.strip() if title_el is not None and title_el.text else chapter_title

            ch_match = _re.match(r"^(\d+)\b", sub_title or "")
            ch_num = int(ch_match.group(1)) if ch_match else chapter_num

            _walk_collection(child, nsmap, repo_path, book_slug, modules,
                             chapter_num=ch_num, chapter_title=sub_title)

        elif tag == "module":
            doc_id = child.get("document", "")
            if not doc_id:
                continue
            title_el = child.find("md:title", nsmap)
            if title_el is None:
                title_el = child.find("col:title", nsmap)
            mod_title = title_el.text.strip() if title_el is not None and title_el.text else doc_id

            module_data = _parse_module(repo_path, doc_id, mod_title,
                                        chapter_num, chapter_title, book_slug)
            if module_data:
                modules.append(module_data)

        else:
            _walk_collection(child, nsmap, repo_path, book_slug, modules,
                             chapter_num, chapter_title)


def _parse_module(
    repo_path, module_id, title, chapter_num, chapter_title, book_slug
) -> dict | None:
    """Parse a single module's index.cnxml and extract text content."""
    cnxml_path = os.path.join(repo_path, "modules", module_id, "index.cnxml")
    if not os.path.isfile(cnxml_path):
        log.warning(f"    Module {module_id} not found at {cnxml_path}")
        return None

    try:
        tree = etree.parse(cnxml_path)
    except etree.XMLSyntaxError as e:
        log.warning(f"    XML parse error in {module_id}: {e}")
        return None

    root = tree.getroot()

    text = etree.tostring(root, method="text", encoding="unicode")
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    if not text or len(text) < 50:
        return None

    learning_objectives = []
    for note in root.iter(f"{{{NS_CNXML}}}note"):
        note_class = note.get("class", "") + " " + note.get("type", "")
        if "learning-objective" in note_class.lower() or "objectives" in note_class.lower():
            obj_text = etree.tostring(note, method="text", encoding="unicode").strip()
            if obj_text:
                learning_objectives.append(obj_text)

    for lst in root.iter(f"{{{NS_CNXML}}}list"):
        lst_class = lst.get("class", "") + " " + lst.get("id", "")
        if "learning-objective" in lst_class.lower() or "objectives" in lst_class.lower():
            obj_text = etree.tostring(lst, method="text", encoding="unicode").strip()
            if obj_text:
                learning_objectives.append(obj_text)

    section_headings = []
    for title_el in root.iter(f"{{{NS_CNXML}}}title"):
        t = title_el.text
        if t and t.strip():
            section_headings.append(t.strip())

    return {
        "module_id": module_id,
        "title": title,
        "chapter": chapter_num,
        "chapter_title": chapter_title,
        "section": f"{chapter_num}",
        "text": text,
        "learning_objectives": learning_objectives,
        "section_headings": section_headings,
        "book_slug": book_slug,
    }


# ---------------------------------------------------------------------------
# Ingest a book via the shared core
# ---------------------------------------------------------------------------

def ingest_book(
    repo_path: str,
    book_slug: str,
    book_uuid: str | None = None,
    content_dir: str = "",
    license_str: str | None = None,
) -> dict:
    """
    Parse a book and ingest all modules via the shared core pipeline.
    Returns dict with sources_created, chunks_created counts.
    """
    subject, grade = get_subject_grade(book_slug)
    modules = parse_book(repo_path, book_slug)

    if not modules:
        log.warning(f"No modules to ingest for {book_slug}")
        return {"sources_created": 0, "chunks_created": 0}

    sources_created = 0
    chunks_created = 0

    for mod in modules:
        chapter_label = mod.get("chapter_title") or f"Ch {mod['chapter']}"
        source_name = f"OpenStax \u2014 {book_slug} \u2014 {chapter_label} \u2014 {mod['title']}"

        if source_exists(source_name):
            log.info(f"  Skipping (exists): {mod['module_id']}")
            continue

        heading = f"{chapter_label} > {mod['title']}"
        sections = [{"page": None, "heading": heading, "text": mod["text"]}]

        result = ingest_sections(
            sections=sections,
            name=source_name,
            subject=subject,
            grade_level=grade,
            upload_lane="openstax",
            file_type="cnxml",
            original_path=f"{content_dir}/{book_slug}/{mod['module_id']}" if content_dir else f"openstax/{book_slug}/{mod['module_id']}",
        )

        if result["status"] == "complete":
            sources_created += 1
            chunks_created += result["chunk_count"]

    # Update license in catalog if available
    if license_str:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE openstax_catalog SET license = %s WHERE book_slug = %s",
                (license_str, book_slug),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    log.info(f"  Book {book_slug}: {sources_created} sources, {chunks_created} chunks total")
    return {"sources_created": sources_created, "chunks_created": chunks_created}
