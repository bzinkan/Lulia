"""
AI Fill Engine — fills custom template canvas with AI-generated content.

Teacher designs a template with fillable areas, then AI Fill generates
content for each area based on standards, topic, and difficulty.
"""
import json
import logging
import os
import re

import anthropic

log = logging.getLogger(__name__)

SONNET = "claude-sonnet-4-20250514"

# Component types and what AI needs to generate for each
FILLABLE_TYPES = {
    "multiple_choice": "question text + 4 answer options (mark correct one)",
    "fill_in_blank": "sentence with ___ blank(s), answer goes in word bank",
    "short_answer": "question requiring 1-2 sentence response",
    "long_answer": "open-ended question requiring paragraph response",
    "true_false": "statement that is clearly true or false",
    "matching": "list of items in left column + matching items in right column",
    "number_problem": "math problem with work space",
    "text_block": "explanatory paragraph about the topic",
    "word_bank": "list of vocabulary words relevant to the topic",
    "vocabulary_box": "term, definition, part of speech, example sentence",
    "definition_card": "key term with its definition",
    "example_box": "worked example showing step-by-step solution",
    "instructions_box": "student-facing instructions for the activity",
    "image_placeholder": "description of a diagram or illustration to generate",
    "table": "data table with headers and sample data",
}


def ai_fill_template(
    canvas_json: dict,
    standards: list[str] | None = None,
    topic: str = "",
    subject: str = "Mathematics",
    grade: str = "4",
    difficulty: str = "medium",
    question_count: int | None = None,
) -> dict:
    """
    Fill a custom template canvas with AI-generated content.

    Identifies fillable components, generates content for each,
    and returns the populated canvas_json.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — AI Fill skipped")
        return canvas_json

    components = canvas_json.get("components", [])
    fillable = []

    for comp in components:
        comp_type = comp.get("type", "")
        if comp_type in FILLABLE_TYPES and not comp.get("content"):
            fillable.append({
                "id": comp.get("id", ""),
                "type": comp_type,
                "label": comp.get("label", ""),
                "expected": FILLABLE_TYPES[comp_type],
            })

    if not fillable:
        log.info("[AI Fill] No fillable components found")
        return canvas_json

    standards_text = ", ".join(standards) if standards else "grade-appropriate"

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        f"Fill these template components with educational content:\n\n"
        f"Subject: {subject}\nGrade: {grade}\nTopic: {topic}\n"
        f"Standards: {standards_text}\nDifficulty: {difficulty}\n\n"
        f"Components to fill:\n"
    )
    for f in fillable:
        prompt += f"- Component '{f['id']}' (type: {f['type']}): Generate {f['expected']}\n"

    prompt += (
        f"\nGenerate a JSON object where keys are component IDs and values are the content.\n"
        f"For multiple_choice: {{\"question\": \"...\", \"options\": [\"A\",\"B\",\"C\",\"D\"], \"correct\": \"A\"}}\n"
        f"For fill_in_blank: {{\"sentence\": \"The ___ is equal to 1/2\", \"answer\": \"fraction\"}}\n"
        f"For text_block: {{\"text\": \"paragraph\"}}\n"
        f"For word_bank: {{\"words\": [\"term1\", \"term2\"]}}\n"
        f"For other types: {{\"content\": \"the content\"}}\n"
        f"Respond with ONLY the JSON object."
    )

    try:
        resp = client.messages.create(
            model=SONNET, max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            filled_data = json.loads(match.group())

            # Apply filled content back to components
            for comp in components:
                comp_id = comp.get("id", "")
                if comp_id in filled_data:
                    comp["content"] = filled_data[comp_id]
                    comp["ai_filled"] = True

            canvas_json["components"] = components
            log.info(f"[AI Fill] Filled {len(filled_data)} components")
    except Exception as e:
        log.error(f"[AI Fill] Failed: {e}")

    return canvas_json


def render_custom_template(canvas_json: dict, theme: str = "modern_clean") -> str:
    """Render a custom template canvas as HTML for preview/print."""
    from src.lms_agents.tools.template_renderer import _base_css

    components = canvas_json.get("components", [])
    name = canvas_json.get("name", "Custom Template")

    body_html = ""
    for comp in components:
        comp_type = comp.get("type", "")
        content = comp.get("content", {})
        label = comp.get("label", "")

        if comp_type == "header":
            title = content.get("title", label) if isinstance(content, dict) else label
            subtitle = content.get("subtitle", "") if isinstance(content, dict) else ""
            body_html += f'<div class="header"><div class="header-left"><h1>{title}</h1><div class="subtitle">{subtitle}</div></div></div>'

        elif comp_type == "name_date_line":
            body_html += '<div class="header-right" style="display:flex;gap:16px;margin-bottom:12px;"><div class="field-line"><span class="field-label">Name:</span><span class="field-blank"></span></div><div class="field-line"><span class="field-label">Date:</span><span class="field-blank"></span></div></div>'

        elif comp_type == "multiple_choice":
            if isinstance(content, dict):
                q = content.get("question", label)
                opts = content.get("options", ["A", "B", "C", "D"])
                body_html += f'<div class="question"><div class="question-text">{q}</div><div class="mc-options">'
                for i, opt in enumerate(opts):
                    letter = chr(65 + i)
                    body_html += f'<div class="option"><span class="option-letter">{letter}.</span> {opt}</div>'
                body_html += '</div></div>'

        elif comp_type == "fill_in_blank":
            if isinstance(content, dict):
                sent = content.get("sentence", label)
                body_html += f'<div class="question"><div class="question-text">{sent}</div></div>'

        elif comp_type in ("short_answer", "long_answer"):
            q = content.get("content", label) if isinstance(content, dict) else label
            lines = 1 if comp_type == "short_answer" else 4
            body_html += f'<div class="question"><div class="question-text">{q}</div><div class="answer-lines-multi">{"".join("<div class=line></div>" for _ in range(lines))}</div></div>'

        elif comp_type == "text_block":
            text = content.get("text", label) if isinstance(content, dict) else label
            body_html += f'<div style="margin-bottom:12px;font-size:13px;color:var(--t-text-secondary);">{text}</div>'

        elif comp_type == "word_bank":
            words = content.get("words", []) if isinstance(content, dict) else []
            words_html = "".join(f'<span class="word-bank-word">{w}</span>' for w in words)
            body_html += f'<div class="word-bank"><div class="word-bank-title">Word Bank</div><div class="word-bank-words">{words_html}</div></div>'

        elif comp_type == "instructions_box":
            text = content.get("content", label) if isinstance(content, dict) else label
            body_html += f'<div class="instructions">{text}</div>'

        elif comp_type == "section_header":
            body_html += f'<h2>{label}</h2>'

        elif comp_type == "divider":
            body_html += '<hr style="border:none;border-top:1px solid var(--t-border);margin:12px 0;">'

        elif comp_type == "image_placeholder":
            desc = content.get("content", "Image") if isinstance(content, dict) else "Image"
            body_html += f'<div style="border:2px dashed var(--t-border);border-radius:14px;min-height:150px;display:flex;align-items:center;justify-content:center;margin-bottom:12px;"><span style="font-size:12px;color:var(--t-text-muted);">{desc}</span></div>'

        elif comp_type == "table":
            body_html += '<div style="border:1px solid var(--t-border);border-radius:10px;min-height:80px;margin-bottom:12px;padding:8px;"><span style="font-size:11px;color:var(--t-text-muted);">Data Table</span></div>'

        else:
            text = str(content) if content else label
            body_html += f'<div style="margin-bottom:8px;font-size:13px;">{text}</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css(theme)}</head>
<body><div class="page">
  {body_html}
  <div class="footer">Generated by Lulia AI — Custom Template</div>
</div></body></html>"""
