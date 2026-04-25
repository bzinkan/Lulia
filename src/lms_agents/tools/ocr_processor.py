"""
OCR Processor — extracts student responses from scanned/photographed assignments.

Uses Claude Sonnet's vision capability to read handwritten and printed text.
Falls back to basic text extraction for digital PDFs.
"""
import base64
import json
import logging
import os
import re

log = logging.getLogger(__name__)


def process_image_with_vision(image_bytes: bytes, assignment_questions: list[dict]) -> dict:
    """
    Use Claude vision to extract student responses from a scanned assignment image.

    PII POLICY (CLAUDE.md decision #10): Student PII is NEVER sent to LLMs. This function
    does NOT ask Claude to read student names. Roster matching happens separately via
    teacher-selected student picker in the grading UI.

    Args:
        image_bytes: raw image bytes (JPEG/PNG)
        assignment_questions: list of question dicts from the assignment

    Returns:
        {
          "responses": {1: "student answer", 2: "student answer", ...},
          "confidence": {1: 0.95, 2: 0.45, ...},
          "flagged": [2],         # question numbers with low confidence
          "student_name": None,   # always null — set by teacher-facing roster picker
        }
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — OCR skipped")
        return {"responses": {}, "confidence": {}, "flagged": [], "student_name": None}

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Build question list for context
    q_list = "\n".join(
        f"Question {q.get('question_number', i+1)}: {q.get('question_text', '')[:80]}"
        for i, q in enumerate(assignment_questions)
    )

    image_b64 = base64.b64encode(image_bytes).decode()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"This is a scanned student assignment. Extract ONLY the answers to the numbered questions.\n\n"
                            f"Questions on this assignment:\n{q_list}\n\n"
                            f"For each question, read the handwritten or typed response.\n"
                            f"IMPORTANT: Do NOT read, extract, or report any names, initials, or other identifying\n"
                            f"information that may appear on the page. Ignore the name field entirely. Focus solely on\n"
                            f"the numbered answers.\n\n"
                            f"Respond with JSON:\n"
                            f"{{\n"
                            f'  "responses": {{"1": "student answer for Q1", "2": "answer for Q2"}},\n'
                            f'  "confidence": {{"1": 0.95, "2": 0.45}},\n'
                            f'  "notes": "any observations about readability (do not mention names)"\n'
                            f"}}\n\n"
                            f"Confidence scale: 1.0=very clear, 0.5=partially readable, 0.0=illegible.\n"
                            f"Respond with ONLY the JSON."
                        ),
                    },
                ],
            }],
        )

        text = response.content[0].text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            result = json.loads(match.group())
            responses = result.get("responses", {})
            confidence = result.get("confidence", {})

            # Flag low-confidence responses
            flagged = []
            for qnum, conf in confidence.items():
                if float(conf) < 0.5:
                    flagged.append(int(qnum))

            return {
                "responses": responses,
                "confidence": confidence,
                "flagged": flagged,
                # student_name intentionally always None — PII never leaves the roster DB.
                # Teacher matches submission to student via picker in the grading UI.
                "student_name": None,
            }

    except Exception as e:
        log.error(f"Vision OCR failed: {e}")

    return {"responses": {}, "confidence": {}, "flagged": [], "student_name": None}


def process_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from a digital PDF (not scanned). Returns plain text."""
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        return text
    except Exception as e:
        log.error(f"PDF text extraction failed: {e}")
        return ""
