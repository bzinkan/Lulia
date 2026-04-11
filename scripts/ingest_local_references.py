"""
Ingest local reference material from a bind-mounted folder.

Walks two folder trees:
  /refs/Teaching/      -> upload_lane='teacher_archive' (Byron's own work)
  /refs/K-8 material/  -> upload_lane='teacher_reference' (reference samples)

Infers grade_band from folder names, subject from second-level folder,
extracts text from PDF/DOCX/PPTX, and feeds every file into the existing
ingest_sections() pipeline (idempotent by source name).

Usage:
  docker compose exec api python scripts/ingest_local_references.py [--dry-run] [--limit N] [--folder teaching|k8|both]
"""
import argparse
import logging
import os
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Ensure src/ is importable
sys.path.insert(0, "/app")

from src.lms_agents.tools.content_ingestion_core import ingest_sections  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ingest_local")

# Byron's teacher account (dev). Change if running against a different env.
TEACHER_ID = "00000000-0000-0000-0000-000000000001"

REFS_ROOT = Path("/refs")
TEACHING_ROOT = REFS_ROOT / "Teaching"
K8_ROOT = REFS_ROOT / "K-8 material"

# File types we know how to extract text from
EXTRACTABLE = {".pdf", ".docx", ".pptx", ".txt"}
# Everything we explicitly skip (binaries, archives, images w/o OCR)
SKIP = {".exe", ".mp4", ".mp3", ".png", ".jpg", ".jpeg", ".gif", ".zip",
        ".doc", ".ppt", ".gdoc", ".gslides", ".xlsx", ".html", ".js",
        ".download", ".loaded_0", ".pptm"}

# -----------------------------------------------------------------------------
# Metadata inference
# -----------------------------------------------------------------------------

GRADE_BAND_PATTERNS = [
    (re.compile(r"\bk[-\s]?2\b", re.I), "K-2"),
    (re.compile(r"\b3[-\s]?5\b", re.I), "3-5"),
    (re.compile(r"\b6[-\s]?8\b", re.I), "6-8"),
    (re.compile(r"\b9[-\s]?12\b", re.I), "9-12"),
    (re.compile(r"\b(kindergarten|1st|2nd)\b", re.I), "K-2"),
    (re.compile(r"\b(3rd|4th|5th)\b", re.I), "3-5"),
    (re.compile(r"\b(6th|7th|8th)\b", re.I), "6-8"),
    (re.compile(r"\b(9th|10th|11th|12th)\b", re.I), "9-12"),
]

# Grade level for standards tagging (single integer string, middle of band)
BAND_TO_GRADE = {"K-2": "1", "3-5": "4", "6-8": "7", "9-12": "10"}

SUBJECT_KEYWORDS = [
    (re.compile(r"\bmath\b", re.I), "Mathematics"),
    (re.compile(r"\b(ela|reading|english|language)\b", re.I), "English Language Arts"),
    (re.compile(r"\b(science|bio|chem|physics|earth|life)\b", re.I), "Science"),
    (re.compile(r"\b(social studies|history|civics|geography)\b", re.I), "Social Studies"),
    (re.compile(r"\brobotics\b", re.I), "Science"),
    (re.compile(r"\bpltw\b", re.I), "Science"),
    (re.compile(r"\bsel\b", re.I), "SEL"),
    (re.compile(r"\b(assessment|games|misc)\b", re.I), "General"),
]


def infer_grade_band(path: Path) -> str:
    """Check folder parts first (highest priority), then full path string."""
    # Priority 1: explicit folder names (k-2, 3-5, 6-8, 9-12)
    for part in path.parts:
        for pat, band in GRADE_BAND_PATTERNS:
            if pat.search(part):
                return band
    # Priority 2: anywhere in full path including filename
    full = path.as_posix()
    for pat, band in GRADE_BAND_PATTERNS:
        if pat.search(full):
            return band
    return "unknown"


def infer_subject(path: Path) -> str:
    # Check folder parts first (more structural)
    for part in path.parts:
        for pat, subj in SUBJECT_KEYWORDS:
            if pat.search(part):
                return subj
    # Then filename/full path
    full = path.as_posix()
    for pat, subj in SUBJECT_KEYWORDS:
        if pat.search(full):
            return subj
    return "General"


# -----------------------------------------------------------------------------
# Text extraction
# -----------------------------------------------------------------------------

def extract_pdf(path: Path) -> list[dict]:
    """Extract per-page text using PyMuPDF (fitz)."""
    import fitz  # PyMuPDF
    sections = []
    try:
        doc = fitz.open(path)
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            text = text.strip()
            if text:
                sections.append({"page": i + 1, "heading": "", "text": text})
        doc.close()
    except Exception as e:
        log.warning(f"  PDF extract failed: {path.name}: {e}")
    return sections


def extract_docx(path: Path) -> list[dict]:
    """Extract paragraphs from a .docx."""
    import docx
    sections = []
    try:
        doc = docx.Document(str(path))
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if paras:
            sections.append({"page": 1, "heading": "", "text": "\n".join(paras)})
    except Exception as e:
        log.warning(f"  DOCX extract failed: {path.name}: {e}")
    return sections


def extract_pptx(path: Path) -> list[dict]:
    """Extract text from .pptx via zip+xml (no python-pptx dependency)."""
    sections = []
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    try:
        with zipfile.ZipFile(path) as z:
            slide_files = sorted(
                [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
            )
            for idx, slide_name in enumerate(slide_files):
                try:
                    with z.open(slide_name) as f:
                        tree = ET.parse(f)
                        texts = []
                        for t in tree.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t"):
                            if t.text:
                                texts.append(t.text.strip())
                        combined = "\n".join([t for t in texts if t])
                        if combined:
                            sections.append(
                                {"page": idx + 1, "heading": f"Slide {idx + 1}", "text": combined}
                            )
                except Exception as e:
                    log.debug(f"    slide parse fail {slide_name}: {e}")
    except Exception as e:
        log.warning(f"  PPTX extract failed: {path.name}: {e}")
    return sections


def extract_txt(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if text:
            return [{"page": 1, "heading": "", "text": text}]
    except Exception as e:
        log.warning(f"  TXT read failed: {path.name}: {e}")
    return []


EXTRACTORS = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".pptx": extract_pptx,
    ".txt": extract_txt,
}

# -----------------------------------------------------------------------------
# Main walk + ingest
# -----------------------------------------------------------------------------

def iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        yield p


def classify(path: Path, lane: str) -> dict:
    rel = path.relative_to(REFS_ROOT)
    band = infer_grade_band(path)
    subject = infer_subject(path)
    # Build a deterministic, readable source name for idempotency
    source_name = f"{lane} — {band} — {subject} — {rel.as_posix()}"
    return {
        "relative_path": str(rel),
        "grade_band": band,
        "grade_level": BAND_TO_GRADE.get(band),
        "subject": subject,
        "upload_lane": lane,
        "source_name": source_name,
    }


def process_file(path: Path, lane: str, dry_run: bool = False) -> dict:
    ext = path.suffix.lower()
    if ext in SKIP:
        return {"status": "skipped_type"}
    if ext not in EXTRACTABLE:
        return {"status": "skipped_unknown", "ext": ext}

    meta = classify(path, lane)

    if dry_run:
        return {"status": "dry", **meta}

    extractor = EXTRACTORS[ext]
    sections = extractor(path)
    if not sections:
        return {"status": "empty", **meta}

    result = ingest_sections(
        sections=sections,
        name=meta["source_name"],
        teacher_id=TEACHER_ID,
        subject=meta["subject"],
        grade_level=meta["grade_level"],
        upload_lane=lane,
        file_type=ext.lstrip("."),
        original_path=str(path),
        scope="teacher",
    )
    return {**meta, **result}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Classify only, no DB writes")
    ap.add_argument("--limit", type=int, default=None, help="Max files to process per root")
    ap.add_argument(
        "--folder",
        choices=["teaching", "k8", "both"],
        default="both",
        help="Which tree to ingest",
    )
    args = ap.parse_args()

    roots = []
    if args.folder in ("teaching", "both"):
        roots.append((TEACHING_ROOT, "teacher_archive"))
    if args.folder in ("k8", "both"):
        roots.append((K8_ROOT, "teacher_reference"))

    totals = {
        "processed": 0,
        "ingested": 0,
        "skipped": 0,
        "empty": 0,
        "errors": 0,
        "by_band": {},
        "by_subject": {},
        "by_lane": {},
    }

    for root, lane in roots:
        if not root.exists():
            log.error(f"Root missing: {root}")
            continue
        log.info(f"=== Walking {root} (lane={lane}) ===")
        count = 0
        for path in iter_files(root):
            if args.limit and count >= args.limit:
                break
            count += 1
            totals["processed"] += 1
            try:
                result = process_file(path, lane, dry_run=args.dry_run)
                status = result.get("status", "?")
                if status in ("complete", "dry"):
                    totals["ingested"] += 1
                    band = result.get("grade_band", "unknown")
                    subject = result.get("subject", "General")
                    totals["by_band"][band] = totals["by_band"].get(band, 0) + 1
                    totals["by_subject"][subject] = totals["by_subject"].get(subject, 0) + 1
                    totals["by_lane"][lane] = totals["by_lane"].get(lane, 0) + 1
                    if totals["processed"] % 25 == 0:
                        log.info(
                            f"  progress: {totals['processed']} processed, "
                            f"{totals['ingested']} ingested"
                        )
                elif status.startswith("skipped"):
                    totals["skipped"] += 1
                elif status == "empty":
                    totals["empty"] += 1
            except Exception as e:
                totals["errors"] += 1
                log.error(f"  ERROR on {path.name}: {e}")

    log.info("=" * 60)
    log.info(f"TOTAL processed: {totals['processed']}")
    log.info(f"  ingested: {totals['ingested']}")
    log.info(f"  skipped:  {totals['skipped']}")
    log.info(f"  empty:    {totals['empty']}")
    log.info(f"  errors:   {totals['errors']}")
    log.info(f"By band:    {totals['by_band']}")
    log.info(f"By subject: {totals['by_subject']}")
    log.info(f"By lane:    {totals['by_lane']}")


if __name__ == "__main__":
    main()
