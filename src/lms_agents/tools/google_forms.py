"""
Google Forms — creates auto-grading quiz forms from assignment content.
"""
import logging

from src.lms_agents.tools.google_auth import get_credentials

log = logging.getLogger(__name__)


def create_quiz_form(
    teacher_id: str,
    title: str,
    questions: list[dict],
    answer_key: dict | None = None,
) -> dict:
    """
    Create a Google Form with quiz settings enabled.
    Returns {form_id, form_url, responder_url}.
    """
    credentials = get_credentials(teacher_id)
    if not credentials:
        raise ValueError("Teacher not connected to Google")

    from googleapiclient.discovery import build

    forms_service = build("forms", "v1", credentials=credentials)

    # Create blank form
    form = forms_service.forms().create(body={
        "info": {"title": title},
    }).execute()
    form_id = form["formId"]

    # Enable quiz mode
    forms_service.forms().batchUpdate(
        formId=form_id,
        body={"requests": [
            {"updateSettings": {
                "settings": {"quizSettings": {"isQuiz": True}},
                "updateMask": "quizSettings.isQuiz",
            }}
        ]},
    ).execute()

    # Add questions
    requests = []
    ak_items = (answer_key or {}).get("answer_key", [])

    for i, q in enumerate(questions):
        qnum = q.get("question_number", i + 1)
        text = q.get("question_text", "")
        answer = q.get("answer", "")
        points = 1

        # Find points from answer key
        for ak in ak_items:
            if ak.get("question_number") == qnum:
                points = ak.get("points", 1)
                break

        # Create as short answer question
        item = {
            "createItem": {
                "item": {
                    "title": f"{qnum}. {text}",
                    "questionItem": {
                        "question": {
                            "required": True,
                            "grading": {
                                "pointValue": points,
                                "correctAnswers": {
                                    "answers": [{"value": answer}]
                                },
                            },
                            "textQuestion": {"paragraph": False},
                        }
                    },
                },
                "location": {"index": i},
            }
        }
        requests.append(item)

    if requests:
        forms_service.forms().batchUpdate(
            formId=form_id, body={"requests": requests}
        ).execute()

    form_url = f"https://docs.google.com/forms/d/{form_id}/edit"
    responder_url = f"https://docs.google.com/forms/d/{form_id}/viewform"

    log.info(f"[Forms] Created quiz: {form_url}")
    return {
        "form_id": form_id,
        "form_url": form_url,
        "responder_url": responder_url,
        "question_count": len(questions),
    }
