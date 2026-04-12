"""
Haiku MCQ question generator for Live Games custom-topic source.

Takes a free-text prompt + grade + subject + count, returns real MCQ questions
with genuine distractors (not placeholder "Not X" strings). Used by
game_session_manager when question_source.type == 'custom'.

Reusable beyond games — any feature that needs cheap, fast MCQ generation
keyed to a topic can call generate_questions().
"""
import json
import logging
import os
import re
from typing import Optional

log = logging.getLogger(__name__)
HAIKU = "claude-haiku-4-5-20251001"


def generate_questions(
    topic: str,
    grade: str = "5",
    subject: str = "General",
    count: int = 15,
    standard_codes: Optional[list[str]] = None,
) -> dict:
    """
    Generate `count` multiple-choice questions on `topic`.

    Returns:
      {
        "success": True,
        "questions": [
          {
            "question": "What is the water cycle?",
            "answer": "The continuous movement of water on Earth",
            "distractors": ["A type of weather", "A kind of rain", "A lake"],
            "standard_code": "5.ESS2.C.1"  # if provided, spread across questions
          },
          ...
        ]
      }
    or {"success": False, "error": str}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"success": False, "error": "ANTHROPIC_API_KEY not set"}

    try:
        import anthropic
    except ImportError:
        return {"success": False, "error": "anthropic package not installed"}

    client = anthropic.Anthropic(api_key=api_key)

    standards_hint = ""
    if standard_codes:
        standards_hint = f"\nThese questions should cover the following standards (distribute across the set):\n  - " + "\n  - ".join(standard_codes)

    system = (
        "You write grade-appropriate multiple-choice questions for K-12 classrooms. "
        "Every question has ONE correct answer and THREE plausible but wrong distractors. "
        "Distractors must be realistic misconceptions a student might genuinely believe — "
        "never placeholders like 'Not X' or 'None of the above'. Output clean JSON only."
    )
    user = f"""Generate {count} multiple-choice questions for Grade {grade} {subject} students.

TOPIC: {topic}
{standards_hint}

Return a JSON array:
[
  {{
    "question": "question stem",
    "answer": "the correct answer",
    "distractors": ["wrong 1", "wrong 2", "wrong 3"],
    "standard_code": "optional matching standard code or null"
  }},
  ...
]

Rules:
- Exactly {count} questions
- 3 distractors per question, each a plausible wrong answer
- Keep answers and distractors similar in length and grammatical form
- Grade-appropriate vocabulary (Grade {grade})
- Mix difficulty across the set (a few easy recall, most medium application, a couple harder)
- Respond with ONLY the JSON array, no preamble"""

    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text.strip()

        # Parse JSON (with tolerant fallback)
        try:
            questions = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\[[\s\S]*\]", text)
            if not match:
                return {"success": False, "error": "Haiku did not return valid JSON"}
            questions = json.loads(match.group())

        if not isinstance(questions, list) or len(questions) == 0:
            return {"success": False, "error": "Empty question list"}

        # Normalize / validate
        normalized = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            question_text = q.get("question", "").strip()
            answer = q.get("answer", "").strip()
            distractors = q.get("distractors", [])
            if not question_text or not answer or not isinstance(distractors, list):
                continue
            normalized.append({
                "question": question_text,
                "answer": answer,
                "distractors": [d.strip() for d in distractors if isinstance(d, str)][:3],
                "standard_code": q.get("standard_code"),
            })

        if not normalized:
            return {"success": False, "error": "No valid questions parsed"}

        return {"success": True, "questions": normalized}
    except Exception as e:
        log.error(f"[QuestionGen] Haiku call failed: {e}")
        return {"success": False, "error": str(e)}
