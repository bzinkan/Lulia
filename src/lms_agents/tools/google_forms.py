"""
Google Forms — creates auto-grading quiz forms.

Uses Gemini Flash (via unified client) for question generation,
then Google Forms API for rendering.
"""
import json
import logging

from src.lms_agents.tools.google_auth import get_credentials
from src.lms_agents.tools.gemini_client import generate_json_with_fallback

log = logging.getLogger(__name__)


def generate_form_questions(
    topic: str,
    standards: list[str],
    grade: str = "4",
    question_count: int = 10,
    question_types: list[str] | None = None,
) -> list[dict]:
    """
    Use Gemini Flash to generate quiz questions for a Google Form.
    Falls back to Claude Haiku if Gemini is unavailable.
    Returns list of question dicts.
    """
    types = question_types or ["multiple_choice", "short_answer"]
    standards_text = ", ".join(standards[:5]) if standards else "grade-appropriate"

    prompt = f"""Generate {question_count} quiz questions for a Google Form.

Topic: {topic}
Grade Level: {grade}
Standards: {standards_text}
Question Types: {', '.join(types)}

Generate a JSON array:
[
  {{
    "question_text": "the question",
    "type": "multiple_choice",
    "options": ["A option", "B option", "C option", "D option"],
    "correct_answer": "A option",
    "points": 2,
    "standard_code": "4.NF.1"
  }},
  {{
    "question_text": "short answer question",
    "type": "short_answer",
    "correct_answer": "the answer",
    "points": 1,
    "standard_code": "4.NF.2"
  }}
]

Generate exactly {question_count} questions with a mix of types.
For multiple_choice: include 4 options with one correct.
For short_answer: provide the expected answer.
All questions must be grade-appropriate for grade {grade}.
Respond with ONLY the JSON array."""

    try:
        result = generate_json_with_fallback(prompt)
        if isinstance(result, list) and len(result) > 0:
            log.info(f"[Forms] Generated {len(result)} questions via Gemini/fallback")
            return result
    except Exception as e:
        log.warning(f"[Forms] Question generation failed: {e}")

    return []


def create_quiz_form(
    teacher_id: str,
    title: str,
    questions: list[dict],
    answer_key: dict | None = None,
) -> dict:
    """
    Create a Google Form with quiz settings enabled.
    Questions can come from generate_form_questions() or from an existing assignment.
    Returns {form_id, form_url, responder_url}.
    """
    credentials = get_credentials(teacher_id)
    if not credentials:
        raise ValueError("Teacher not connected to Google")

    from googleapiclient.discovery import build

    forms_service = build("forms", "v1", credentials=credentials)

    form = forms_service.forms().create(body={"info": {"title": title}}).execute()
    form_id = form["formId"]

    # Enable quiz mode
    forms_service.forms().batchUpdate(
        formId=form_id,
        body={"requests": [
            {"updateSettings": {"settings": {"quizSettings": {"isQuiz": True}}, "updateMask": "quizSettings.isQuiz"}}
        ]},
    ).execute()

    # Add questions
    requests = []
    ak_items = (answer_key or {}).get("answer_key", [])

    for i, q in enumerate(questions):
        qnum = q.get("question_number", i + 1)
        text = q.get("question_text", "")
        answer = q.get("correct_answer", q.get("answer", ""))
        q_type = q.get("type", "short_answer")
        points = q.get("points", 1)

        for ak in ak_items:
            if ak.get("question_number") == qnum:
                points = ak.get("points", points)
                answer = ak.get("correct_answer", answer)
                break

        if q_type == "multiple_choice" and q.get("options"):
            item = {
                "createItem": {
                    "item": {
                        "title": f"{qnum}. {text}",
                        "questionItem": {
                            "question": {
                                "required": True,
                                "grading": {"pointValue": points, "correctAnswers": {"answers": [{"value": answer}]}},
                                "choiceQuestion": {"type": "RADIO", "options": [{"value": opt} for opt in q["options"]]},
                            }
                        },
                    },
                    "location": {"index": i},
                }
            }
        else:
            item = {
                "createItem": {
                    "item": {
                        "title": f"{qnum}. {text}",
                        "questionItem": {
                            "question": {
                                "required": True,
                                "grading": {"pointValue": points, "correctAnswers": {"answers": [{"value": answer}]}},
                                "textQuestion": {"paragraph": False},
                            }
                        },
                    },
                    "location": {"index": i},
                }
            }
        requests.append(item)

    if requests:
        forms_service.forms().batchUpdate(formId=form_id, body={"requests": requests}).execute()

    form_url = f"https://docs.google.com/forms/d/{form_id}/edit"
    responder_url = f"https://docs.google.com/forms/d/{form_id}/viewform"

    log.info(f"[Forms] Created quiz: {form_url} ({len(questions)} questions)")
    return {"form_id": form_id, "form_url": form_url, "responder_url": responder_url, "question_count": len(questions)}
