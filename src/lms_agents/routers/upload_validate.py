"""
Upload validation — two-layer approach.

Layer 1 (deterministic): Can our system parse this file format?
Layer 2 (Claude Haiku):  Is the content actually what the teacher thinks it is?

For standards specifically:
  - JSON with correct structure → fast-track, skip Haiku
  - PDF/DOCX/TXT → readable, but Haiku checks if content looks like standards
  - Unreadable file → hard reject

For curriculum/materials:
  - Any readable format (PDF/DOCX/TXT) → Haiku sanity-checks content
  - Unreadable → hard reject
"""
import json
import logging
import os
import re
import tempfile

import anthropic
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

HAIKU = "claude-haiku-4-5-20251001"

READABLE_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md", "json", "csv"}

# What each upload type should look like
DOCUMENT_PROFILES = {
    "standards": {
        "label": "Educational Standards Document",
        "description": (
            "A document containing educational standards, learning objectives, "
            "or benchmarks organized by grade level and subject. Typically includes "
            "standard codes (like 4.NF.1 or OH.SC.6.ES.1), descriptions of what "
            "students should know or be able to do, and organization by grade and "
            "subject/domain. Could be from a state department of education, a "
            "diocese, a charter network, or a school district. May also be called "
            "learning standards, performance indicators, benchmarks, or objectives."
        ),
        "reject_examples": [
            "individual lesson plans or worksheets",
            "textbook chapters or reading passages",
            "student work samples or grade sheets",
            "administrative documents (attendance, discipline)",
            "pacing guides (those go under Curriculum)",
        ],
    },
    "curriculum": {
        "label": "Curriculum / Pacing Guide",
        "description": (
            "A document outlining a curriculum sequence, pacing guide, scope and "
            "sequence, or unit plan organized by weeks or time periods. Typically "
            "includes units/topics mapped to specific weeks or dates, standards "
            "covered per unit, and sometimes suggested activities or assessments."
        ),
        "reject_examples": [
            "individual worksheets or tests",
            "textbook chapters",
            "standalone lesson plans (not a full pacing guide)",
            "standards documents without pacing/sequencing",
        ],
    },
    "materials": {
        "label": "Teaching Materials",
        "description": (
            "Teaching materials such as worksheets, textbook chapters, lesson "
            "plans, activity instructions, study guides, lab procedures, reading "
            "passages, or reference documents that a teacher would use in their "
            "classroom. These become searchable in the Knowledge Base."
        ),
        "reject_examples": [
            "personal documents (resumes, letters)",
            "administrative forms (attendance, discipline)",
            "student personal information or grades",
            "software documentation or code",
        ],
    },
}


def _extract_text_preview(content: bytes, filename: str, max_chars: int = 3000) -> str:
    """Extract the first N chars of text from a file for validation."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("json", "txt", "md", "csv"):
        return content.decode("utf-8", errors="ignore")[:max_chars]

    if ext == "pdf":
        try:
            import fitz  # PyMuPDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                doc = fitz.open(tmp_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                    if len(text) > max_chars:
                        break
                doc.close()
                return text[:max_chars]
            finally:
                os.unlink(tmp_path)
        except ImportError:
            return content[:max_chars].decode("utf-8", errors="ignore")
        except Exception as e:
            log.warning(f"PDF text extraction failed: {e}")
            return ""

    if ext in ("docx", "doc"):
        try:
            from docx import Document
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                doc = Document(tmp_path)
                text = "\n".join(p.text for p in doc.paragraphs)
                return text[:max_chars]
            finally:
                os.unlink(tmp_path)
        except ImportError:
            return content[:max_chars].decode("utf-8", errors="ignore")
        except Exception as e:
            log.warning(f"DOCX text extraction failed: {e}")
            return ""

    return content[:max_chars].decode("utf-8", errors="ignore")


def _check_json_standards_structure(content: bytes) -> dict | None:
    """
    Check if JSON content has the expected standards structure.
    Returns the parsed data if valid, None if not.
    """
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    # Check for our expected structure
    if isinstance(data, dict):
        standards = data.get("standards", [])
        if isinstance(standards, list) and len(standards) > 0:
            first = standards[0]
            if isinstance(first, dict) and ("code" in first or "description" in first):
                return data

    return None


def _get_haiku_client() -> anthropic.Anthropic | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _extract_json_from_response(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


@router.post("/validate")
async def validate_upload(
    file: UploadFile = File(...),
    upload_type: str = Form(...),
):
    """
    Two-layer validation before upload.

    Layer 1 (deterministic): file format, readability, structure checks.
    Layer 2 (Haiku): content classification — is this actually what they think?

    Returns:
        {
            "valid": bool,
            "confidence": float,
            "detected_type": str,
            "message": str,
            "proceed": bool,
            "hard_reject": bool,  // if true, frontend should not offer "upload anyway"
            "format_info": str,   // details about format issues if any
        }
    """
    if upload_type not in DOCUMENT_PROFILES:
        return JSONResponse(
            {"error": f"Unknown upload type: {upload_type}"},
            status_code=400,
        )

    profile = DOCUMENT_PROFILES[upload_type]
    content = await file.read()
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # ── LAYER 1: Format & readability checks ──

    # Check file extension
    if ext not in READABLE_EXTENSIONS:
        return {
            "valid": False,
            "confidence": 1.0,
            "detected_type": "unknown",
            "message": f"Unsupported file format: .{ext}. Please upload a PDF, DOCX, TXT, or JSON file.",
            "proceed": False,
            "hard_reject": True,
            "format_info": f"Supported formats: {', '.join(sorted(READABLE_EXTENSIONS))}",
        }

    # Standards-specific: JSON fast-track
    if upload_type == "standards" and ext == "json":
        parsed = _check_json_standards_structure(content)
        if parsed:
            count = len(parsed.get("standards", []))
            fw_name = parsed.get("framework", {}).get("name", "Custom")
            return {
                "valid": True,
                "confidence": 1.0,
                "detected_type": "standards",
                "message": f"Valid standards JSON detected: {fw_name} ({count} standards). Ready to upload.",
                "proceed": True,
                "hard_reject": False,
                "format_info": "JSON with correct structure — fast-track approved.",
            }
        else:
            # JSON but wrong structure
            return {
                "valid": False,
                "confidence": 0.9,
                "detected_type": "unknown",
                "message": (
                    "This JSON file doesn't have the expected standards structure. "
                    "Standards JSON should have a 'standards' array where each item "
                    "has 'code' and 'description' fields. If you have standards in "
                    "a different format, try uploading as PDF or DOCX instead — "
                    "we'll extract the standards automatically."
                ),
                "proceed": False,
                "hard_reject": True,
                "format_info": 'Expected: {"framework": {...}, "standards": [{"code": "...", "description": "..."}]}',
            }

    # Extract text preview for readability check
    preview = _extract_text_preview(content, filename)
    if not preview or len(preview.strip()) < 30:
        return {
            "valid": False,
            "confidence": 1.0,
            "detected_type": "unknown",
            "message": (
                "Could not extract readable text from this file. "
                "The file may be scanned/image-only, password-protected, or corrupted. "
                "Please upload a text-based PDF, DOCX, or TXT file."
            ),
            "proceed": False,
            "hard_reject": True,
            "format_info": "No readable text extracted.",
        }

    # ── LAYER 2: Haiku content classification ──

    client = _get_haiku_client()
    if not client:
        # No API key — skip content check, allow upload
        return {
            "valid": True,
            "confidence": 0.5,
            "detected_type": upload_type,
            "message": "Format looks good. Content validation skipped (no API key).",
            "proceed": True,
            "hard_reject": False,
            "format_info": f"Readable {ext.upper()} file, {len(preview)} chars extracted.",
        }

    system = (
        "You are a document classifier for an educational LMS called Lulia Lesson Lab. "
        "A teacher is uploading a document. Your job is to determine whether it matches "
        "the expected upload type. Be helpful and accurate — teachers upload standards "
        "from many different sources (states, dioceses, charter networks, school districts) "
        "in many different formats. A standards document might look very different from one "
        "school to the next. Focus on whether the CONTENT is the right type, not whether "
        "the FORMAT is perfect."
    )

    user = f"""A teacher is uploading this document as: **{profile['label']}**

Expected document characteristics:
{profile['description']}

Documents that should NOT be uploaded as {profile['label']}:
{chr(10).join(f'- {ex}' for ex in profile['reject_examples'])}

--- DOCUMENT PREVIEW (first portion) ---
Filename: {filename}
{preview[:2500]}
--- END PREVIEW ---

Classify this document. Respond with ONLY a JSON object:
{{
  "matches_expected_type": true/false,
  "confidence": 0.0-1.0,
  "detected_type": "standards|curriculum|materials|unknown",
  "reason": "One sentence explaining your classification"
}}"""

    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        result = _extract_json_from_response(resp.content[0].text)

        if not result:
            result = {
                "matches_expected_type": True,
                "confidence": 0.5,
                "detected_type": upload_type,
                "reason": "Could not parse validation response",
            }

        matches = result.get("matches_expected_type", True)
        confidence = float(result.get("confidence", 0.5))
        detected = result.get("detected_type", upload_type)
        reason = result.get("reason", "")

        if matches:
            # For standards from PDF/DOCX, note that Haiku will extract them
            extraction_note = ""
            if upload_type == "standards" and ext != "json":
                extraction_note = " We'll automatically extract the individual standards from your document."

            return {
                "valid": True,
                "confidence": confidence,
                "detected_type": detected,
                "message": f"This looks like a valid {profile['label'].lower()}.{extraction_note} {reason}",
                "proceed": True,
                "hard_reject": False,
                "format_info": f"Readable {ext.upper()}, {len(preview)} chars.",
            }
        else:
            # Content mismatch — warn but allow for curriculum/materials,
            # hard reject is False so teacher can override
            suggestion = ""
            if detected != "unknown" and detected != upload_type:
                type_labels = {
                    "standards": "Upload Standards",
                    "curriculum": "Upload Curriculum",
                    "materials": "Upload Materials",
                }
                suggestion = f" Try the \"{type_labels.get(detected, detected)}\" button instead."

            return {
                "valid": False,
                "confidence": confidence,
                "detected_type": detected,
                "message": f"This doesn't look like a {profile['label'].lower()}. {reason}{suggestion}",
                "proceed": False,
                "hard_reject": False,
                "format_info": f"Readable {ext.upper()}, content classified as: {detected}.",
            }

    except Exception as e:
        log.warning(f"[Validate] Haiku call failed: {e}")
        return {
            "valid": True,
            "confidence": 0.5,
            "detected_type": upload_type,
            "message": "Format looks good. Content check unavailable — proceeding.",
            "proceed": True,
            "hard_reject": False,
            "format_info": f"Readable {ext.upper()}, Haiku check skipped.",
        }
