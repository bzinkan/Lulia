"""
Answer Matcher — compares student responses to answer keys.

Supports multiple question types:
  - Multiple choice: exact match
  - Numerical: tolerance-based with fraction/decimal/percent support
  - Short answer: key concept matching via Claude Haiku
  - Essay: rubric-based scoring (AI-assisted, not AI-decided)
"""
import json
import logging
import os
import re

log = logging.getLogger(__name__)


def match_multiple_choice(response: str, correct: str) -> dict:
    """Exact match for MC questions. Returns {correct, points_earned, feedback}."""
    r = response.strip().upper()[:1]
    c = correct.strip().upper()[:1]
    is_correct = r == c
    return {
        "correct": is_correct,
        "points_earned": 1.0 if is_correct else 0.0,
        "points_possible": 1.0,
        "feedback": "Correct!" if is_correct else f"The correct answer is {c}.",
    }


def _parse_number(s: str) -> float | None:
    """Parse a number from various formats: 0.5, 1/2, 50%, etc."""
    s = s.strip().replace(",", "")
    # Percentage
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100
        except ValueError:
            pass
    # Fraction
    if "/" in s:
        parts = s.split("/")
        try:
            return float(parts[0].strip()) / float(parts[1].strip())
        except (ValueError, ZeroDivisionError):
            pass
    # Mixed number (e.g., "2 1/3")
    mixed = re.match(r"(\d+)\s+(\d+)/(\d+)", s)
    if mixed:
        try:
            return int(mixed.group(1)) + int(mixed.group(2)) / int(mixed.group(3))
        except (ValueError, ZeroDivisionError):
            pass
    # Decimal
    try:
        return float(s)
    except ValueError:
        return None


def match_numerical(response: str, correct: str, tolerance: float = 0.01) -> dict:
    """Number matching with fraction/decimal/percent support."""
    r_val = _parse_number(response)
    c_val = _parse_number(correct)

    if r_val is None:
        return {
            "correct": False,
            "points_earned": 0.0,
            "points_possible": 1.0,
            "feedback": f"Could not parse your answer. The correct answer is {correct}.",
        }
    if c_val is None:
        return {"correct": False, "points_earned": 0.0, "points_possible": 1.0, "feedback": ""}

    is_correct = abs(r_val - c_val) <= tolerance
    return {
        "correct": is_correct,
        "points_earned": 1.0 if is_correct else 0.0,
        "points_possible": 1.0,
        "feedback": "Correct!" if is_correct else f"The correct answer is {correct}.",
    }


def match_short_answer(response: str, correct: str, key_concepts: list[str] | None = None, threshold: float = 0.7) -> dict:
    """
    Semantic match for short answers using Claude Haiku.
    Falls back to keyword matching if API unavailable.
    """
    if not response.strip():
        return {"correct": False, "points_earned": 0.0, "points_possible": 1.0, "feedback": "No response provided."}

    # Try Claude Haiku for semantic matching
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": (
                    f"Compare this student response to the correct answer. "
                    f"Student: \"{response}\"\nCorrect: \"{correct}\"\n"
                    f"Respond with JSON: {{\"score\": 0.0-1.0, \"feedback\": \"brief feedback\"}}"
                )}],
            )
            text = resp.content[0].text
            match = re.search(r"\{[^}]+\}", text)
            if match:
                result = json.loads(match.group())
                score = float(result.get("score", 0))
                return {
                    "correct": score >= threshold,
                    "points_earned": round(score, 2),
                    "points_possible": 1.0,
                    "feedback": result.get("feedback", ""),
                }
        except Exception as e:
            log.warning(f"Claude matching failed: {e}")

    # Fallback: keyword matching
    response_lower = response.lower()
    correct_lower = correct.lower()
    keywords = key_concepts or correct_lower.split()
    matches = sum(1 for kw in keywords if kw in response_lower)
    score = matches / max(len(keywords), 1)
    return {
        "correct": score >= threshold,
        "points_earned": round(score, 2),
        "points_possible": 1.0,
        "feedback": "Correct!" if score >= threshold else f"Expected key concepts: {correct[:80]}",
    }


def match_essay(response: str, rubric: dict, max_points: int = 4) -> dict:
    """
    Rubric-based essay scoring. Returns AI-assisted score (teacher should confirm).
    """
    if not response.strip():
        return {"correct": False, "points_earned": 0, "points_possible": max_points, "feedback": "No response.", "needs_review": True}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"correct": False, "points_earned": 0, "points_possible": max_points, "feedback": "AI grading unavailable", "needs_review": True}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": (
                f"Score this student essay response on a {max_points}-point rubric.\n"
                f"Rubric: {json.dumps(rubric)}\n"
                f"Response: \"{response[:2000]}\"\n"
                f"Respond with JSON: {{\"score\": 0-{max_points}, \"feedback\": \"detailed feedback\", \"strengths\": [\"...\"], \"improvements\": [\"...\"]}}"
            )}],
        )
        text = resp.content[0].text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            result = json.loads(match.group())
            score = min(float(result.get("score", 0)), max_points)
            return {
                "correct": score >= max_points * 0.7,
                "points_earned": round(score, 1),
                "points_possible": max_points,
                "feedback": result.get("feedback", ""),
                "needs_review": True,  # Always flag essays for teacher review
            }
    except Exception as e:
        log.warning(f"Essay grading failed: {e}")

    return {"correct": False, "points_earned": 0, "points_possible": max_points, "feedback": "Could not grade", "needs_review": True}


def grade_question(response: str, correct: str, question_type: str = "auto", **kwargs) -> dict:
    """
    Auto-detect question type and grade accordingly.

    question_type: 'mc', 'numerical', 'short_answer', 'essay', 'auto'
    """
    if question_type == "mc" or (question_type == "auto" and len(correct.strip()) == 1 and correct.strip().isalpha()):
        return match_multiple_choice(response, correct)
    elif question_type == "numerical" or (question_type == "auto" and _parse_number(correct) is not None and len(correct.strip()) < 15):
        return match_numerical(response, correct, kwargs.get("tolerance", 0.01))
    elif question_type == "essay":
        return match_essay(response, kwargs.get("rubric", {}), kwargs.get("max_points", 4))
    else:
        return match_short_answer(response, correct, kwargs.get("key_concepts"), kwargs.get("threshold", 0.7))
