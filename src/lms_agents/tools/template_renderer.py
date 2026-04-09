"""
Template Renderer — fills HTML templates with structured content JSON.

Each template in src/lms_agents/templates/{template_id}/ has:
  - template.html: the base HTML with CSS (used as reference only)
  - config.json: parameters like questions_per_page, layout_type, etc.

The renderer builds complete HTML documents from content data using
Python string formatting. Templates are self-contained (inline CSS,
print-ready, no external dependencies).

Questions may carry a structured `visual` field that the visual_renderer
module converts into inline SVG. This replaces the older pattern of LLMs
embedding bracketed text like "[Image: ten-frame with 5 dots]" in
question_text — see visual_renderer.py for the supported types.
"""
import json
import logging
import os
from pathlib import Path

from src.lms_agents.tools.visual_renderer import get_visual_css, render_visual

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
THEMES_DIR = TEMPLATES_DIR / "shared_themes"

# Module-level theme state — set by render_template(), read by _base_css()
_current_theme = "modern_clean"


def get_template_config(template_id: str) -> dict:
    """Load config.json for a template."""
    config_path = TEMPLATES_DIR / template_id / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


THEMES = {
    "modern_clean": {
        "name": "Modern Clean",
        "primary": "#F97316", "primary_light": "#FB923C", "primary_lighter": "#FDBA74",
        "primary_lightest": "#FED7AA", "primary_bg": "#FFF7ED", "primary_dark": "#EA580C",
        "primary_darkest": "#9A3412",
        "heading_font": "'DM Serif Display', serif", "body_font": "'DM Sans', sans-serif",
        "bg": "#FFFFFF", "bg_tint": "#FEF9F2", "text": "#1C1917", "text_secondary": "#78716C",
        "text_muted": "#A8A29E", "border": "#E7E5E4", "border_light": "#F5F5F4",
        "success": "#16A34A", "success_bg": "#DCFCE7",
    },
    "playful_primary": {
        "name": "Playful Primary",
        "primary": "#E11D48", "primary_light": "#FB7185", "primary_lighter": "#FECDD3",
        "primary_lightest": "#FFF1F2", "primary_bg": "#FFF1F2", "primary_dark": "#BE123C",
        "primary_darkest": "#881337",
        "heading_font": "'Fredoka', 'DM Sans', sans-serif", "body_font": "'DM Sans', sans-serif",
        "bg": "#FFFFFF", "bg_tint": "#FFFBEB", "text": "#1C1917", "text_secondary": "#78716C",
        "text_muted": "#A8A29E", "border": "#FECDD3", "border_light": "#FFF1F2",
        "success": "#16A34A", "success_bg": "#DCFCE7",
    },
    "bold_bright": {
        "name": "Bold & Bright",
        "primary": "#7C3AED", "primary_light": "#A78BFA", "primary_lighter": "#C4B5FD",
        "primary_lightest": "#EDE9FE", "primary_bg": "#F5F3FF", "primary_dark": "#6D28D9",
        "primary_darkest": "#4C1D95",
        "heading_font": "'DM Serif Display', serif", "body_font": "'DM Sans', sans-serif",
        "bg": "#FFFFFF", "bg_tint": "#F5F3FF", "text": "#1C1917", "text_secondary": "#6B7280",
        "text_muted": "#9CA3AF", "border": "#C4B5FD", "border_light": "#EDE9FE",
        "success": "#059669", "success_bg": "#D1FAE5",
    },
    "nature_earth": {
        "name": "Nature & Earth",
        "primary": "#059669", "primary_light": "#34D399", "primary_lighter": "#6EE7B7",
        "primary_lightest": "#D1FAE5", "primary_bg": "#ECFDF5", "primary_dark": "#047857",
        "primary_darkest": "#064E3B",
        "heading_font": "'DM Serif Display', serif", "body_font": "'DM Sans', sans-serif",
        "bg": "#FFFFFF", "bg_tint": "#F0FDF4", "text": "#1C1917", "text_secondary": "#6B7280",
        "text_muted": "#9CA3AF", "border": "#6EE7B7", "border_light": "#D1FAE5",
        "success": "#B45309", "success_bg": "#FEF3C7",
    },
}


def _base_css(theme: str | None = None) -> str:
    """Shared CSS for all templates with theme support via CSS custom properties."""
    t = THEMES.get(theme or _current_theme, THEMES["modern_clean"])
    css_vars = (
        f"@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700&family=Fredoka:wght@400;500;600&display=swap');\n"
        f":root {{\n"
        f"  --t-primary: {t['primary']}; --t-primary-light: {t['primary_light']};\n"
        f"  --t-primary-lighter: {t['primary_lighter']}; --t-primary-lightest: {t['primary_lightest']};\n"
        f"  --t-primary-bg: {t['primary_bg']}; --t-primary-dark: {t['primary_dark']};\n"
        f"  --t-primary-darkest: {t['primary_darkest']};\n"
        f"  --t-heading-font: {t['heading_font']}; --t-body-font: {t['body_font']};\n"
        f"  --t-bg: {t['bg']}; --t-bg-tint: {t['bg_tint']};\n"
        f"  --t-text: {t['text']}; --t-text-secondary: {t['text_secondary']};\n"
        f"  --t-text-muted: {t['text_muted']}; --t-border: {t['border']};\n"
        f"  --t-border-light: {t['border_light']};\n"
        f"  --t-success: {t['success']}; --t-success-bg: {t['success_bg']};\n"
        f"}}\n"
    )
    return """
    <style>
      """ + css_vars + """
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body {
        font-family: var(--t-body-font);
        font-size: 14px;
        color: var(--t-text);
        line-height: 1.6;
        background: var(--t-bg);
      }
      .page {
        width: 8.5in;
        min-height: 11in;
        padding: 0.6in 0.7in;
        margin: 0 auto;
        position: relative;
      }
      h1, h2, h3 { font-family: var(--t-heading-font); }
      h1 { font-size: 22px; margin-bottom: 4px; }
      h2 { font-size: 16px; margin-bottom: 8px; color: var(--t-primary-darkest); }
      h3 { font-size: 13px; margin-bottom: 4px; }
      .header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        border-bottom: 2px solid var(--t-primary);
        padding-bottom: 10px;
        margin-bottom: 16px;
      }
      .header-left h1 { color: var(--t-text); }
      .header-left .subtitle { font-size: 12px; color: var(--t-text-secondary); margin-top: 2px; }
      .header-right {
        text-align: right;
        font-size: 12px;
        color: var(--t-text-secondary);
      }
      .header-right .field-line {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 4px;
        justify-content: flex-end;
      }
      .header-right .field-label { font-weight: 600; color: var(--t-primary-darkest); font-size: 11px; }
      .header-right .field-blank {
        border-bottom: 1px solid var(--t-border);
        width: 140px;
        display: inline-block;
        height: 18px;
      }
      .standards-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 14px;
      }
      .standard-badge {
        font-size: 10px;
        padding: 2px 8px;
        border-radius: 4px;
        background: var(--t-primary-bg);
        color: var(--t-primary-darkest);
        border: 1px solid var(--t-primary-lighter);
        font-weight: 500;
      }
      .instructions {
        background: var(--t-primary-bg);
        border-left: 3px solid var(--t-primary);
        padding: 8px 12px;
        font-size: 12px;
        color: var(--t-primary-darkest);
        margin-bottom: 16px;
        border-radius: 0 8px 8px 0;
      }
      .question {
        margin-bottom: 14px;
        page-break-inside: avoid;
      }
      .question-number {
        font-weight: 700;
        color: var(--t-primary);
        margin-right: 6px;
      }
      .question-text { font-size: 13px; color: var(--t-text); }
      .answer-line {
        border-bottom: 1px solid var(--t-border);
        height: 24px;
        margin-top: 6px;
        margin-left: 20px;
      }
      .answer-lines-multi {
        margin-top: 6px;
        margin-left: 20px;
      }
      .answer-lines-multi .line {
        border-bottom: 1px solid var(--t-border);
        height: 22px;
      }
      .mc-options {
        margin-top: 4px;
        margin-left: 20px;
        font-size: 13px;
      }
      .mc-options .option { margin-bottom: 2px; }
      .mc-options .option-letter { font-weight: 600; color: var(--t-primary-darkest); margin-right: 8px; }
      .word-bank {
        border: 1px solid var(--t-border);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 16px;
        background: var(--t-bg-tint);
      }
      .word-bank-title { font-size: 11px; font-weight: 600; color: var(--t-primary-darkest); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
      .word-bank-words { display: flex; flex-wrap: wrap; gap: 8px; }
      .word-bank-word { font-size: 13px; color: var(--t-text); padding: 2px 10px; background: white; border-radius: 6px; border: 1px solid var(--t-primary-lighter); }
      .difficulty-badge {
        display: inline-block;
        font-size: 9px;
        padding: 1px 6px;
        border-radius: 4px;
        font-weight: 600;
        margin-left: 6px;
        text-transform: uppercase;
      }
      .diff-easy { background: #DCFCE7; color: #16A34A; }
      .diff-medium { background: #FEF3C7; color: #D97706; }
      .diff-hard { background: #FEF2F2; color: #EF4444; }
      .points { font-size: 10px; color: var(--t-text-muted); float: right; }
      .answer-key-answer { color: var(--t-success); font-weight: 600; }
      .footer {
        position: absolute;
        bottom: 0.4in;
        left: 0.7in;
        right: 0.7in;
        text-align: center;
        font-size: 9px;
        color: var(--t-text-muted);
        border-top: 1px solid var(--t-border-light);
        padding-top: 6px;
      }
      /* Print */
      @media print {
        body { background: white; }
        .page { padding: 0.5in 0.6in; margin: 0; box-shadow: none; }
        .no-print { display: none; }
        @page { margin: 0; size: letter; }
      }
      /* Card grid */
      .card-grid {
        display: grid;
        gap: 12px;
      }
      .card-grid-6 { grid-template-columns: repeat(2, 1fr); }
      .card-grid-8 { grid-template-columns: repeat(2, 1fr); }
      .card {
        border: 1px solid var(--t-border);
        border-radius: 12px;
        padding: 14px;
        page-break-inside: avoid;
        position: relative;
      }
      .card-number {
        position: absolute;
        top: 8px;
        right: 10px;
        font-size: 10px;
        font-weight: 700;
        color: var(--t-primary);
        background: var(--t-primary-bg);
        border-radius: 50%;
        width: 22px;
        height: 22px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .cut-line {
        border-top: 1px dashed #D6D3D1;
        margin: 8px 0;
      }
      /* Bingo */
      .bingo-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        border: 2px solid var(--t-primary);
        border-radius: 10px;
        overflow: hidden;
      }
      .bingo-cell {
        border: 1px solid var(--t-border);
        padding: 10px 4px;
        text-align: center;
        font-size: 11px;
        min-height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .bingo-header {
        background: var(--t-primary);
        color: white;
        font-family: var(--t-heading-font);
        font-size: 18px;
        font-weight: 700;
        padding: 8px;
      }
      .bingo-free {
        background: var(--t-primary-bg);
        font-weight: 700;
        color: var(--t-primary);
        font-size: 14px;
      }
      /* Passage */
      .passage {
        background: var(--t-bg-tint);
        border: 1px solid var(--t-border);
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 16px;
        font-size: 13px;
        line-height: 1.8;
      }
      .passage .line-number {
        display: inline-block;
        width: 24px;
        text-align: right;
        margin-right: 10px;
        color: var(--t-text-muted);
        font-size: 10px;
        user-select: none;
      }
      .vocab-sidebar {
        background: #FFF7ED;
        border-radius: 10px;
        padding: 12px;
        font-size: 12px;
      }
      .vocab-sidebar .vocab-word { font-weight: 600; color: var(--t-primary-darkest); }
      .vocab-sidebar .vocab-def { color: var(--t-text-secondary); margin-left: 4px; }
      /* Two-column for reading comp */
      .two-col { display: grid; grid-template-columns: 1fr 200px; gap: 16px; }
      /* Half-page */
      .half-page { min-height: 5.25in; max-height: 5.5in; overflow: hidden; }
      .half-divider { border-top: 2px dashed var(--t-border); margin: 8px 0; }
      /* Graphic organizer */
      .go-venn { display: flex; justify-content: center; gap: 0; margin: 20px 0; }
      .go-circle {
        width: 200px;
        height: 200px;
        border-radius: 50%;
        border: 2px solid #F97316;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
        font-size: 11px;
        text-align: center;
      }
      .go-circle:nth-child(2) { margin-left: -40px; }
      .go-tchart {
        display: grid;
        grid-template-columns: 1fr 1fr;
        border: 2px solid var(--t-primary);
        border-radius: 10px;
        overflow: hidden;
      }
      .go-tchart-header {
        background: var(--t-primary-bg);
        padding: 8px;
        font-weight: 600;
        text-align: center;
        border-bottom: 2px solid var(--t-primary);
        font-family: var(--t-heading-font);
      }
      .go-tchart-cell {
        padding: 12px;
        min-height: 200px;
        border-right: 1px solid #E7E5E4;
      }
      .go-kwl {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        border: 2px solid var(--t-primary);
        border-radius: 10px;
        overflow: hidden;
      }
      .study-topic {
        background: #FFF7ED;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
      }
      .study-vocab { font-weight: 600; color: var(--t-primary); }
      .study-example {
        background: var(--t-bg-tint);
        border-left: 3px solid var(--t-primary-lighter);
        padding: 8px 12px;
        margin: 8px 0;
        font-size: 12px;
        border-radius: 0 8px 8px 0;
      }
      """ + get_visual_css() + """
    </style>
"""


def render_worksheet(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render a worksheet template."""
    title = content.get("title", "Worksheet")
    instructions = content.get("instructions", "")
    questions = content.get("questions", [])
    standards = list({q.get("standard_code", "") for q in questions if q.get("standard_code")})
    word_bank_items = content.get("word_bank", [])

    standards_html = "".join(f'<span class="standard-badge">{s}</span>' for s in sorted(standards))

    word_bank_html = ""
    if word_bank_items:
        words = "".join(f'<span class="word-bank-word">{w}</span>' for w in word_bank_items)
        word_bank_html = f'<div class="word-bank"><div class="word-bank-title">Word Bank</div><div class="word-bank-words">{words}</div></div>'

    questions_html = ""
    for q in questions:
        num = q.get("question_number", "")
        text = q.get("question_text", "")
        diff = q.get("difficulty", "")
        pts = q.get("points", 1)
        diff_badge = f'<span class="difficulty-badge diff-{diff}">{diff}</span>' if diff and answer_key else ""
        pts_html = f'<span class="points">{pts} pt{"s" if pts > 1 else ""}</span>' if answer_key else ""

        visual_html = render_visual(q.get("visual"))

        answer_html = ""
        if answer_key:
            ans = q.get("answer", "")
            answer_html = f'<div style="margin-top:4px;margin-left:20px;"><span class="answer-key-answer">{ans}</span></div>'
        else:
            answer_html = '<div class="answer-line"></div>'

        questions_html += f"""
        <div class="question">
          <div><span class="question-number">{num}.</span><span class="question-text">{text}</span>{diff_badge}{pts_html}</div>
          {visual_html}
          {answer_html}
        </div>"""

    ak_label = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header">
    <div class="header-left"><h1>{title}{ak_label}</h1><div class="subtitle">Standards-Aligned Assessment</div></div>
    <div class="header-right">
      <div class="field-line"><span class="field-label">Name:</span><span class="field-blank"></span></div>
      <div class="field-line"><span class="field-label">Date:</span><span class="field-blank"></span></div>
      <div class="field-line"><span class="field-label">Class:</span><span class="field-blank"></span></div>
    </div>
  </div>
  <div class="standards-bar">{standards_html}</div>
  <div class="instructions">{instructions}</div>
  {word_bank_html}
  {questions_html}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_task_cards(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render task cards — 6 per page with answer cards on separate page."""
    title = content.get("title", "Task Cards")
    questions = content.get("questions", [])

    cards_html = ""
    for q in questions:
        num = q.get("question_number", "")
        text = q.get("question_text", "")
        visual_html = render_visual(q.get("visual"))
        if answer_key:
            ans = q.get("answer", "")
            cards_html += f"""
            <div class="card">
              <div class="card-number">{num}</div>
              <div class="question-text" style="margin-bottom:8px;">{text}</div>
              {visual_html}
              <div class="answer-key-answer">{ans}</div>
            </div>"""
        else:
            cards_html += f"""
            <div class="card">
              <div class="card-number">{num}</div>
              <div class="question-text" style="padding-right:20px;">{text}</div>
              {visual_html}
            </div>"""

    ak_label = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header">
    <div class="header-left"><h1>{title}{ak_label}</h1></div>
  </div>
  <div class="card-grid card-grid-6">{cards_html}</div>
  <div class="footer">Generated by Lulia AI &middot; Cut along card borders</div>
</div></body></html>"""


def render_exit_ticket(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render exit tickets — 2 per page (half-page format)."""
    title = content.get("title", "Exit Ticket")
    questions = content.get("questions", [])[:5]

    def ticket_html(is_answer):
        qs = ""
        for q in questions:
            num = q.get("question_number", "")
            text = q.get("question_text", "")
            visual_html = render_visual(q.get("visual"))
            if is_answer:
                ans = q.get("answer", "")
                qs += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span>{visual_html}<div style="margin-left:20px;margin-top:2px;"><span class="answer-key-answer">{ans}</span></div></div>'
            else:
                qs += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span>{visual_html}<div class="answer-line"></div></div>'
        ak = " — ANSWER KEY" if is_answer else ""
        return f"""
        <div class="half-page">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #F97316;padding-bottom:6px;margin-bottom:10px;">
            <div><h2 style="margin:0;">{title}{ak}</h2></div>
            <div style="text-align:right;font-size:11px;color:#78716C;">
              <div>Name: <span style="border-bottom:1px solid #E7E5E4;width:100px;display:inline-block;">&nbsp;</span></div>
              <div>Date: <span style="border-bottom:1px solid #E7E5E4;width:100px;display:inline-block;">&nbsp;</span></div>
            </div>
          </div>
          {qs}
        </div>"""

    if answer_key:
        body = ticket_html(True)
    else:
        body = ticket_html(False) + '<div class="half-divider"></div>' + ticket_html(False)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">{body}<div class="footer">Generated by Lulia AI</div></div></body></html>"""


def render_quiz_test(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render formal quiz/test layout with point values."""
    title = content.get("title", "Quiz")
    instructions = content.get("instructions", "Read each question carefully. Show all work.")
    questions = content.get("questions", [])
    standards = list({q.get("standard_code", "") for q in questions if q.get("standard_code")})
    total_points = sum(q.get("points", 1) for q in questions)

    standards_html = "".join(f'<span class="standard-badge">{s}</span>' for s in sorted(standards))

    questions_html = ""
    for q in questions:
        num = q.get("question_number", "")
        text = q.get("question_text", "")
        pts = q.get("points", 1)
        pts_html = f'<span class="points">/{pts}</span>'
        visual_html = render_visual(q.get("visual"))

        if answer_key:
            ans = q.get("answer", "")
            answer_html = f'<div style="margin-top:4px;margin-left:20px;"><span class="answer-key-answer">{ans}</span></div>'
        else:
            answer_html = '<div class="answer-lines-multi"><div class="line"></div><div class="line"></div></div>'

        questions_html += f"""
        <div class="question">
          <div><span class="question-number">{num}.</span><span class="question-text">{text}</span>{pts_html}</div>
          {visual_html}
          {answer_html}
        </div>"""

    ak_label = " — ANSWER KEY" if answer_key else ""
    score_box = f'<div style="border:2px solid #F97316;border-radius:10px;padding:8px 14px;text-align:center;"><div style="font-size:10px;color:#78350F;font-weight:600;">SCORE</div><div style="font-size:20px;font-weight:700;color:#1C1917;">__/{total_points}</div></div>' if not answer_key else f'<div style="font-size:12px;color:#78350F;font-weight:600;">Total: {total_points} points</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header">
    <div class="header-left"><h1>{title}{ak_label}</h1><div class="subtitle">Assessment</div></div>
    <div class="header-right">
      <div class="field-line"><span class="field-label">Name:</span><span class="field-blank"></span></div>
      <div class="field-line"><span class="field-label">Date:</span><span class="field-blank"></span></div>
      {score_box}
    </div>
  </div>
  <div class="standards-bar">{standards_html}</div>
  <div class="instructions">{instructions}</div>
  {questions_html}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_flashcards(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render flashcards — 8 per page, front then back."""
    title = content.get("title", "Flashcards")
    questions = content.get("questions", [])

    fronts = ""
    backs = ""
    for q in questions:
        num = q.get("question_number", "")
        text = q.get("question_text", "")
        ans = q.get("answer", "")
        fronts += f'<div class="card" style="text-align:center;display:flex;align-items:center;justify-content:center;min-height:100px;"><div><div class="card-number">{num}</div><div style="font-size:14px;font-weight:500;">{text}</div></div></div>'
        backs += f'<div class="card" style="text-align:center;display:flex;align-items:center;justify-content:center;min-height:100px;background:#FFF7ED;"><div><div class="card-number">{num}</div><div class="answer-key-answer" style="font-size:14px;">{ans}</div></div></div>'

    if answer_key:
        body = f'<h2>Answer Side</h2><div class="card-grid card-grid-8">{backs}</div>'
    else:
        body = f'<h2>Front (Terms)</h2><div class="card-grid card-grid-8">{fronts}</div><div style="page-break-before:always;"></div><h2>Back (Definitions)</h2><div class="card-grid card-grid-8">{backs}</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}</h1><div class="subtitle">Cut along card borders</div></div></div>
  {body}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_bingo(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render a BINGO card with 5x5 grid."""
    title = content.get("title", "BINGO")
    questions = content.get("questions", [])
    # Use answers as bingo terms
    terms = [q.get("answer", q.get("question_text", "")) for q in questions]
    while len(terms) < 24:
        terms.append(f"Term {len(terms)+1}")
    terms = terms[:24]  # Need exactly 24 (25 - FREE)

    # Insert FREE in center (position 12)
    cells = terms[:12] + ["FREE"] + terms[12:]

    bingo_letters = "BINGO"
    header = "".join(f'<div class="bingo-header">{l}</div>' for l in bingo_letters)
    grid_cells = ""
    for i, cell in enumerate(cells):
        if cell == "FREE":
            grid_cells += '<div class="bingo-cell bingo-free">FREE</div>'
        else:
            grid_cells += f'<div class="bingo-cell">{cell}</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div style="text-align:center;margin-bottom:16px;">
    <h1 style="font-size:28px;">{title}</h1>
    <div style="font-size:11px;color:#78716C;">Name: _________________ Date: _____________</div>
  </div>
  <div class="bingo-grid" style="max-width:500px;margin:0 auto;">
    {header}{grid_cells}
  </div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_graphic_organizer(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render graphic organizer — T-chart, Venn, or KWL."""
    title = content.get("title", "Graphic Organizer")
    layout = content.get("layout_type", config.get("layout_type", "tchart"))
    questions = content.get("questions", [])

    body = ""
    if layout == "venn":
        left = content.get("venn_left", "Category A")
        right = content.get("venn_right", "Category B")
        body = f"""
        <div class="go-venn">
          <div class="go-circle" style="background:rgba(249,115,22,0.05);">{left}</div>
          <div class="go-circle" style="background:rgba(34,197,94,0.05);">{right}</div>
        </div>"""
    elif layout == "kwl":
        body = """
        <div class="go-kwl">
          <div><div class="go-tchart-header">K — What I Know</div><div class="go-tchart-cell"></div></div>
          <div><div class="go-tchart-header">W — What I Want to Know</div><div class="go-tchart-cell" style="border-left:1px solid #E7E5E4;border-right:1px solid #E7E5E4;"></div></div>
          <div><div class="go-tchart-header">L — What I Learned</div><div class="go-tchart-cell"></div></div>
        </div>"""
    else:  # tchart
        left = content.get("tchart_left", "Category A")
        right = content.get("tchart_right", "Category B")
        body = f"""
        <div class="go-tchart">
          <div class="go-tchart-header">{left}</div>
          <div class="go-tchart-header">{right}</div>
          <div class="go-tchart-cell"></div>
          <div class="go-tchart-cell"></div>
        </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}</h1></div>
    <div class="header-right"><div class="field-line"><span class="field-label">Name:</span><span class="field-blank"></span></div></div>
  </div>
  {body}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_morning_work(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render morning work / bell ringer — compact, 3-5 problems + challenge."""
    title = content.get("title", "Morning Work")
    questions = content.get("questions", [])
    regular = questions[:-1] if len(questions) > 3 else questions
    challenge = questions[-1] if len(questions) > 3 else None

    qs_html = ""
    for q in regular:
        num = q.get("question_number", "")
        text = q.get("question_text", "")
        visual_html = render_visual(q.get("visual"))
        if answer_key:
            ans = q.get("answer", "")
            qs_html += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span>{visual_html}<div style="margin-left:20px;margin-top:2px;"><span class="answer-key-answer">{ans}</span></div></div>'
        else:
            qs_html += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span>{visual_html}<div class="answer-line"></div></div>'

    challenge_html = ""
    if challenge:
        ch_text = challenge.get("question_text", "")
        ch_visual = render_visual(challenge.get("visual"))
        if answer_key:
            ch_ans = challenge.get("answer", "")
            challenge_html = f'<div style="background:#FFF7ED;border:2px solid #F97316;border-radius:10px;padding:12px;margin-top:12px;"><h3 style="color:#F97316;margin-bottom:4px;">Challenge</h3><div class="question-text">{ch_text}</div>{ch_visual}<div style="margin-top:4px;"><span class="answer-key-answer">{ch_ans}</span></div></div>'
        else:
            challenge_html = f'<div style="background:#FFF7ED;border:2px solid #F97316;border-radius:10px;padding:12px;margin-top:12px;"><h3 style="color:#F97316;margin-bottom:4px;">Challenge</h3><div class="question-text">{ch_text}</div>{ch_visual}<div class="answer-line"></div></div>'

    ak = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #F97316;padding-bottom:8px;margin-bottom:12px;">
    <h1>{title}{ak}</h1>
    <div style="font-size:11px;color:#78716C;">Name: _____________ Date: ___________</div>
  </div>
  {qs_html}
  {challenge_html}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_study_guide(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render study guide — organized by topic with vocabulary and practice."""
    title = content.get("title", "Study Guide")
    questions = content.get("questions", [])
    standards = list({q.get("standard_code", "") for q in questions if q.get("standard_code")})

    standards_html = "".join(f'<span class="standard-badge">{s}</span>' for s in sorted(standards))

    # Group by standard
    by_standard = {}
    for q in questions:
        std = q.get("standard_code", "General")
        by_standard.setdefault(std, []).append(q)

    sections_html = ""
    for std, qs in by_standard.items():
        qs_html = ""
        for q in qs:
            num = q.get("question_number", "")
            text = q.get("question_text", "")
            if answer_key:
                ans = q.get("answer", "")
                exp = q.get("explanation", "")
                qs_html += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span><div class="study-example"><span class="answer-key-answer">{ans}</span>{" — " + exp if exp else ""}</div></div>'
            else:
                qs_html += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span><div class="answer-line"></div></div>'

        sections_html += f'<div class="study-topic"><h3>{std}</h3>{qs_html}</div>'

    ak = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}{ak}</h1><div class="subtitle">Review &amp; Practice</div></div>
    <div class="header-right"><div class="field-line"><span class="field-label">Name:</span><span class="field-blank"></span></div></div>
  </div>
  <div class="standards-bar">{standards_html}</div>
  {sections_html}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_reading_comprehension(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render reading comprehension — passage with line numbers + questions."""
    title = content.get("title", "Reading Comprehension")
    passage = content.get("passage", content.get("instructions", ""))
    questions = content.get("questions", [])
    vocabulary = content.get("vocabulary", [])

    # Add line numbers to passage
    lines = passage.split("\n") if passage else []
    if len(lines) <= 1 and passage:
        # Split long text into ~80 char lines
        words = passage.split()
        lines = []
        current = ""
        for w in words:
            if len(current) + len(w) > 80:
                lines.append(current.strip())
                current = w + " "
            else:
                current += w + " "
        if current.strip():
            lines.append(current.strip())

    passage_html = ""
    for i, line in enumerate(lines, 1):
        passage_html += f'<div><span class="line-number">{i}</span>{line}</div>'

    vocab_html = ""
    if vocabulary:
        vocab_items = "".join(f'<div style="margin-bottom:6px;"><span class="vocab-word">{v.get("term", v)}</span><span class="vocab-def">— {v.get("definition", "")}</span></div>' for v in vocabulary)
        vocab_html = f'<div class="vocab-sidebar"><h3 style="margin-bottom:8px;">Vocabulary</h3>{vocab_items}</div>'

    qs_html = ""
    for q in questions:
        num = q.get("question_number", "")
        text = q.get("question_text", "")
        if answer_key:
            ans = q.get("answer", "")
            qs_html += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span><div style="margin-left:20px;margin-top:2px;"><span class="answer-key-answer">{ans}</span></div></div>'
        else:
            qs_html += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span><div class="answer-lines-multi"><div class="line"></div><div class="line"></div></div></div>'

    ak = " — Answer Key" if answer_key else ""
    if vocab_html:
        content_area = f'<div class="two-col"><div><div class="passage">{passage_html}</div>{qs_html}</div>{vocab_html}</div>'
    else:
        content_area = f'<div class="passage">{passage_html}</div>{qs_html}'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}{ak}</h1></div>
    <div class="header-right">
      <div class="field-line"><span class="field-label">Name:</span><span class="field-blank"></span></div>
      <div class="field-line"><span class="field-label">Date:</span><span class="field-blank"></span></div>
    </div>
  </div>
  {content_area}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def render_word_search(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render a word search puzzle."""
    from src.lms_agents.tools.puzzle_generators import generate_word_search

    title = content.get("title", "Word Search")
    questions = content.get("questions", [])
    words = [q.get("answer", q.get("question_text", "")) for q in questions]
    words = [w for w in words if w and len(w) <= 15]
    grid_size = config.get("grid_size", 15)

    puzzle = generate_word_search(words, grid_size=grid_size)
    grid = puzzle["solution_grid"] if answer_key else puzzle["grid"]

    grid_html = '<table style="border-collapse:collapse;margin:0 auto;">'
    for r, row in enumerate(grid):
        grid_html += "<tr>"
        for c, cell in enumerate(row):
            # In answer key, highlight placed letters
            bg = ""
            if answer_key and puzzle["solution_grid"][r][c] != ".":
                bg = "background:#FFF7ED;font-weight:700;color:#F97316;"
            display = cell if cell != "." else ""
            grid_html += f'<td style="width:28px;height:28px;text-align:center;font-size:14px;font-family:monospace;border:1px solid #E7E5E4;{bg}">{display}</td>'
        grid_html += "</tr>"
    grid_html += "</table>"

    words_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;justify-content:center;">'
    for w in puzzle["words"]:
        strike = "text-decoration:line-through;color:#A8A29E;" if answer_key else ""
        words_html += f'<span style="font-size:13px;font-weight:500;padding:2px 10px;border:1px solid #E7E5E4;border-radius:6px;{strike}">{w}</span>'
    words_html += "</div>"

    ak = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div style="text-align:center;margin-bottom:16px;">
    <h1>{title}{ak}</h1>
    <div style="font-size:11px;color:#78716C;">Name: _________________ Date: _____________</div>
    <p style="font-size:12px;color:#78350F;margin-top:8px;">Find all {len(puzzle['words'])} hidden words in the grid below!</p>
  </div>
  {grid_html}
  {words_html}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_crossword(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render a crossword puzzle."""
    from src.lms_agents.tools.puzzle_generators import generate_crossword

    title = content.get("title", "Crossword")
    questions = content.get("questions", [])
    clues = [{"clue": q.get("question_text", ""), "answer": q.get("answer", "")} for q in questions]

    puzzle = generate_crossword(clues, grid_size=config.get("grid_size", 20))
    grid = puzzle["solution_grid"] if answer_key else puzzle["grid"]
    numbers = puzzle["numbers_grid"]

    # Trim grid to used area
    min_r, max_r, min_c, max_c = 999, 0, 999, 0
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] is not None:
                min_r, max_r = min(min_r, r), max(max_r, r)
                min_c, max_c = min(min_c, c), max(max_c, c)
    if min_r > max_r:
        min_r, max_r, min_c, max_c = 0, 10, 0, 10

    grid_html = '<table style="border-collapse:collapse;margin:0 auto;">'
    for r in range(min_r, max_r + 1):
        grid_html += "<tr>"
        for c in range(min_c, max_c + 1):
            cell = grid[r][c]
            num = numbers[r][c]
            if cell is None:
                grid_html += '<td style="width:28px;height:28px;background:#1C1917;"></td>'
            else:
                num_html = f'<span style="position:absolute;top:1px;left:2px;font-size:8px;color:#A8A29E;">{num}</span>' if num else ""
                display = cell if answer_key else ""
                grid_html += f'<td style="width:28px;height:28px;border:1px solid #E7E5E4;position:relative;text-align:center;font-size:14px;font-weight:600;">{num_html}{display}</td>'
        grid_html += "</tr>"
    grid_html += "</table>"

    across_html = "<div style='margin-top:16px;'><h3 style='color:#F97316;'>Across</h3>"
    for c in puzzle["across_clues"]:
        across_html += f"<div style='font-size:12px;margin:2px 0;'><strong>{c['number']}.</strong> {c['clue']}</div>"
    across_html += "</div>"

    down_html = "<div style='margin-top:12px;'><h3 style='color:#F97316;'>Down</h3>"
    for c in puzzle["down_clues"]:
        down_html += f"<div style='font-size:12px;margin:2px 0;'><strong>{c['number']}.</strong> {c['clue']}</div>"
    down_html += "</div>"

    ak = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div style="text-align:center;margin-bottom:12px;">
    <h1>{title}{ak}</h1>
    <div style="font-size:11px;color:#78716C;">Name: _________________ Date: _____________</div>
  </div>
  {grid_html}
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">{across_html}{down_html}</div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_board_game(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render a board game with a path of spaces."""
    from src.lms_agents.tools.puzzle_generators import generate_board_game

    title = content.get("title", "Board Game")
    questions = content.get("questions", [])
    total = config.get("total_spaces", 36)

    puzzle = generate_board_game(questions, total_spaces=total)

    # Render as a grid of spaces
    cols = 6
    spaces_html = '<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:6px;">'
    for s in puzzle["spaces"]:
        if s["type"] == "start":
            bg = "background:#F97316;color:white;font-weight:700;"
        elif s["type"] == "finish":
            bg = "background:#22C55E;color:white;font-weight:700;"
        elif s["type"] == "question":
            bg = "background:#FFF7ED;border:2px solid #F97316;"
        elif s["type"] == "special":
            bg = "background:#FEF3C7;border:1px solid #D97706;"
        else:
            bg = "background:white;border:1px solid #E7E5E4;"
        label = s["label"][:20]
        spaces_html += f'<div style="border-radius:10px;padding:8px 4px;text-align:center;font-size:10px;min-height:50px;display:flex;align-items:center;justify-content:center;{bg}">{label}</div>'
    spaces_html += "</div>"

    # Question cards
    q_cards = ""
    q_spaces = [s for s in puzzle["spaces"] if s["type"] == "question"]
    for s in q_spaces:
        ans_html = f'<div class="answer-key-answer" style="margin-top:4px;">{s["answer"]}</div>' if answer_key else ""
        q_cards += f'<div class="card"><div class="card-number">{s["label"]}</div><div class="question-text">{s["question"]}</div>{ans_html}</div>'

    ak = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}{ak}</h1><div class="subtitle">{puzzle['instructions']}</div></div></div>
  {spaces_html}
  <div style="margin-top:16px;"><h2>Question Cards</h2></div>
  <div class="card-grid card-grid-6">{q_cards}</div>
  <div class="footer">Generated by Lulia AI &middot; Needs: 1 die, game pieces</div>
</div></body></html>"""


def render_scavenger_hunt(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render scavenger hunt clue cards + teacher guide."""
    from src.lms_agents.tools.puzzle_generators import generate_scavenger_hunt

    title = content.get("title", "Scavenger Hunt")
    questions = content.get("questions", [])

    puzzle = generate_scavenger_hunt(questions)

    if answer_key:
        # Teacher guide
        guide_html = ""
        for s in puzzle["stations"]:
            guide_html += f"""
            <div class="card" style="margin-bottom:8px;">
              <div class="card-number">{s['station_number']}</div>
              <div style="font-size:11px;color:#F97316;font-weight:600;">Location: {s['location']}</div>
              <div class="question-text" style="margin:4px 0;">{s['question']}</div>
              <div class="answer-key-answer">{s['answer']}</div>
            </div>"""
        setup = "<br>".join(puzzle["teacher_setup"])
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title} — Teacher Guide</h1></div></div>
  <div class="instructions">Setup Instructions:<br>{setup}</div>
  {guide_html}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""
    else:
        # Student clue cards
        cards = ""
        for s in puzzle["stations"]:
            cards += f"""
            <div class="card">
              <div class="card-number">{s['station_number']}</div>
              <div style="font-size:11px;color:#F97316;font-weight:600;">Station {s['station_number']}</div>
              <div class="question-text" style="margin:6px 0;">{s['question']}</div>
              <div class="answer-line"></div>
              <div style="margin-top:8px;font-size:11px;color:#78716C;font-style:italic;">{s['next_clue']}</div>
            </div>"""
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div style="text-align:center;margin-bottom:12px;">
    <h1>{title}</h1>
    <p style="font-size:12px;color:#78350F;">{puzzle['instructions']}</p>
    <div style="font-size:11px;color:#78716C;margin-top:4px;">Name: _________________ Date: _____________</div>
  </div>
  <div class="card-grid card-grid-6">{cards}</div>
  <div class="footer">Generated by Lulia AI &middot; Cut cards and place at locations</div>
</div></body></html>"""


def render_escape_room(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render escape room puzzle cards + recording sheet."""
    from src.lms_agents.tools.puzzle_generators import generate_escape_room

    title = content.get("title", "Escape Room")
    questions = content.get("questions", [])
    num_stages = config.get("num_stages", 4)

    puzzle = generate_escape_room(questions, num_stages=num_stages)

    if answer_key:
        guide = ""
        for s in puzzle["stages"]:
            guide += f"""
            <div class="card" style="margin-bottom:8px;">
              <div class="card-number">{s['stage_number']}</div>
              <h3>{s['name']}</h3>
              <div class="question-text" style="margin:4px 0;">{s['question']}</div>
              <div class="answer-key-answer">Answer: {s['answer']}</div>
              <div style="font-size:11px;color:#F97316;font-weight:600;">Code digit: {s['code_digit']}</div>
            </div>"""
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title} — Teacher Guide</h1></div></div>
  <div style="background:#FFF7ED;border:2px solid #F97316;border-radius:14px;padding:12px;text-align:center;margin-bottom:16px;">
    <div style="font-size:12px;color:#78350F;font-weight:600;">FINAL LOCK CODE</div>
    <div style="font-size:28px;font-weight:700;color:#F97316;letter-spacing:8px;">{puzzle['final_code']}</div>
  </div>
  {guide}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""
    else:
        stages = ""
        for s in puzzle["stages"]:
            stages += f"""
            <div class="card" style="margin-bottom:8px;">
              <div class="card-number">{s['stage_number']}</div>
              <h3>{s['name']}</h3>
              <div style="font-size:11px;color:#78716C;margin-bottom:4px;">{s['description']}</div>
              <div class="question-text" style="margin:6px 0;">{s['question']}</div>
              <div class="answer-line"></div>
              <div style="margin-top:6px;font-size:11px;color:#F97316;">Code digit #{s['stage_number']}: ____</div>
            </div>"""

        code_boxes = "".join(f'<div style="width:40px;height:50px;border:2px solid #F97316;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;font-size:24px;margin:0 4px;">&nbsp;</div>' for _ in puzzle["stages"])

        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div style="text-align:center;margin-bottom:12px;">
    <h1>{title}</h1>
    <p style="font-size:12px;color:#78350F;">{puzzle['instructions']}</p>
    <div style="font-size:11px;color:#78716C;margin-top:4px;">Name: _________________ Date: _____________</div>
  </div>
  {stages}
  <div style="text-align:center;margin-top:16px;padding:16px;border:2px solid #F97316;border-radius:14px;background:#FFF7ED;">
    <div style="font-size:12px;font-weight:600;color:#78350F;margin-bottom:8px;">ENTER THE LOCK CODE</div>
    {code_boxes}
  </div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_vocab_cards(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render tiered vocabulary cards — word, definition, part of speech, example sentence. 8 per page."""
    title = content.get("title", "Vocabulary Cards")
    questions = content.get("questions", [])

    cards = ""
    for q in questions:
        word = q.get("question_text", "")
        definition = q.get("answer", "")
        explanation = q.get("explanation", "")
        num = q.get("question_number", "")
        cards += f"""
        <div class="card" style="padding:12px;">
          <div class="card-number">{num}</div>
          <div style="font-family:var(--t-heading-font);font-size:16px;color:var(--t-text);margin-bottom:4px;">{word}</div>
          <div style="font-size:11px;color:var(--t-text-secondary);margin-bottom:6px;"><strong>Definition:</strong> {definition}</div>
          <div style="font-size:11px;color:var(--t-text-muted);font-style:italic;">{explanation}</div>
          {'<div style="margin-top:6px;height:40px;border:1px dashed var(--t-border);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:9px;color:var(--t-text-muted);">illustration</div>' if not answer_key else ''}
        </div>"""

    ak = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}{ak}</h1><div class="subtitle">Cut along card borders</div></div></div>
  <div class="card-grid card-grid-8">{cards}</div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_anchor_chart(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render anchor chart — large-format reference poster."""
    title = content.get("title", "Anchor Chart")
    questions = content.get("questions", [])
    instructions = content.get("instructions", "")

    key_points = ""
    for q in questions[:6]:
        text = q.get("question_text", "")
        ans = q.get("answer", "")
        key_points += f'<div style="margin-bottom:10px;padding:8px 12px;background:var(--t-primary-bg);border-radius:10px;"><div style="font-weight:600;color:var(--t-text);font-size:14px;">{text}</div><div style="font-size:12px;color:var(--t-text-secondary);margin-top:2px;">{ans}</div></div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page" style="border:3px solid var(--t-primary);border-radius:16px;">
  <div style="text-align:center;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid var(--t-primary);">
    <h1 style="font-size:28px;">{title}</h1>
    <p style="font-size:13px;color:var(--t-text-secondary);">{instructions}</p>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
    <div>{key_points}</div>
    <div style="border:2px dashed var(--t-border);border-radius:14px;display:flex;align-items:center;justify-content:center;min-height:200px;"><span style="font-size:12px;color:var(--t-text-muted);">Visual / Diagram Area</span></div>
  </div>
  <div style="margin-top:16px;background:var(--t-primary-lightest);border:2px solid var(--t-primary-lighter);border-radius:14px;padding:14px;text-align:center;">
    <h3 style="color:var(--t-primary);margin-bottom:4px;">Remember!</h3>
    <p style="font-size:13px;color:var(--t-primary-darkest);">{questions[-1].get('answer', '') if questions else 'Key takeaway goes here'}</p>
  </div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_homework_packet(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render multi-page weekly homework packet. Mon-Thu + Friday review."""
    title = content.get("title", "Homework Packet")
    questions = content.get("questions", [])

    days = ["Monday", "Tuesday", "Wednesday", "Thursday"]
    per_day = max(1, len(questions) // 5) if len(questions) >= 5 else len(questions)

    pages = ""
    q_idx = 0
    for day in days:
        day_qs = ""
        for j in range(per_day):
            if q_idx >= len(questions):
                break
            q = questions[q_idx]
            q_idx += 1
            if answer_key:
                day_qs += f'<div class="question"><span class="question-number">{q.get("question_number", "")}.</span><span class="question-text">{q.get("question_text", "")}</span><div style="margin-left:20px;margin-top:2px;"><span class="answer-key-answer">{q.get("answer", "")}</span></div></div>'
            else:
                day_qs += f'<div class="question"><span class="question-number">{q.get("question_number", "")}.</span><span class="question-text">{q.get("question_text", "")}</span><div class="answer-line"></div></div>'
        pages += f'<div style="margin-bottom:20px;"><h2>{day}</h2>{day_qs}</div>'

    # Friday review with remaining questions
    friday_qs = ""
    while q_idx < len(questions):
        q = questions[q_idx]
        q_idx += 1
        if answer_key:
            friday_qs += f'<div class="question"><span class="question-number">{q.get("question_number", "")}.</span><span class="question-text">{q.get("question_text", "")}</span><div style="margin-left:20px;margin-top:2px;"><span class="answer-key-answer">{q.get("answer", "")}</span></div></div>'
        else:
            friday_qs += f'<div class="question"><span class="question-number">{q.get("question_number", "")}.</span><span class="question-text">{q.get("question_text", "")}</span><div class="answer-line"></div></div>'
    if friday_qs:
        pages += f'<div style="margin-bottom:20px;"><h2>Friday Review</h2>{friday_qs}</div>'

    ak = " — Answer Key" if answer_key else ""
    sig_line = '' if answer_key else '<div style="margin-top:20px;border-top:1px solid var(--t-border);padding-top:8px;font-size:11px;color:var(--t-text-muted);">Parent/Guardian Signature: _________________________ Date: __________</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}{ak}</h1><div class="subtitle">Weekly Practice</div></div>
    <div class="header-right"><div class="field-line"><span class="field-label">Name:</span><span class="field-blank"></span></div></div>
  </div>
  {pages}
  {sig_line}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_sub_plans(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render substitute teacher plans."""
    title = content.get("title", "Substitute Teacher Plans")
    instructions = content.get("instructions", "")
    questions = content.get("questions", [])

    activities = ""
    for q in questions:
        activities += f'<div style="margin-bottom:10px;padding:10px;background:var(--t-primary-bg);border-radius:10px;"><div style="font-weight:600;color:var(--t-text);">{q.get("question_text", "")}</div><div style="font-size:12px;color:var(--t-text-secondary);margin-top:2px;">{q.get("answer", "")}</div></div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}</h1><div class="subtitle">Emergency Lesson Plan</div></div>
    <div class="header-right"><div class="field-line"><span class="field-label">Date:</span><span class="field-blank"></span></div><div class="field-line"><span class="field-label">Sub Name:</span><span class="field-blank"></span></div></div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
    <div style="background:var(--t-bg-tint);border-radius:10px;padding:10px;"><h3>Schedule Overview</h3><div style="font-size:12px;color:var(--t-text-secondary);">{instructions or 'See posted schedule'}</div></div>
    <div style="background:var(--t-bg-tint);border-radius:10px;padding:10px;"><h3>Seating Chart</h3><div style="font-size:11px;color:var(--t-text-muted);">See posted seating chart at front of room</div></div>
  </div>
  <h2>Activities</h2>
  {activities}
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px;">
    <div style="background:var(--t-primary-bg);border:1px solid var(--t-primary-lighter);border-radius:10px;padding:10px;"><h3 style="color:var(--t-primary);">Early Finishers</h3><p style="font-size:12px;color:var(--t-text-secondary);">Silent reading, vocabulary review, or enrichment worksheet in the sub folder.</p></div>
    <div style="background:var(--t-bg-tint);border:1px solid var(--t-border);border-radius:10px;padding:10px;"><h3>Behavior Notes</h3><div style="min-height:60px;"></div></div>
  </div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_parent_newsletter(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render parent newsletter — what we learned, upcoming, vocabulary, ways to help."""
    title = content.get("title", "Classroom Newsletter")
    instructions = content.get("instructions", "")
    questions = content.get("questions", [])

    learned = questions[:3] if len(questions) >= 3 else questions
    upcoming = questions[3:6] if len(questions) >= 6 else []
    vocab = questions[6:] if len(questions) > 6 else []

    learned_html = "<ul style='font-size:12px;color:var(--t-text-secondary);padding-left:16px;'>" + "".join(f"<li style='margin-bottom:4px;'>{q.get('question_text', '')}</li>" for q in learned) + "</ul>"
    upcoming_html = "<ul style='font-size:12px;color:var(--t-text-secondary);padding-left:16px;'>" + "".join(f"<li style='margin-bottom:4px;'>{q.get('question_text', '')}</li>" for q in upcoming) + "</ul>" if upcoming else "<p style='font-size:12px;color:var(--t-text-muted);'>Stay tuned!</p>"
    vocab_html = "<div style='display:flex;flex-wrap:wrap;gap:6px;'>" + "".join(f"<span class='word-bank-word'>{q.get('answer', q.get('question_text', ''))}</span>" for q in vocab) + "</div>" if vocab else ""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div style="text-align:center;border-bottom:3px solid var(--t-primary);padding-bottom:12px;margin-bottom:16px;">
    <h1 style="font-size:26px;">{title}</h1>
    <p style="font-size:12px;color:var(--t-text-secondary);">{instructions}</p>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div><h2 style="margin-bottom:6px;">What We Learned</h2>{learned_html}</div>
    <div><h2 style="margin-bottom:6px;">Coming Up Next</h2>{upcoming_html}</div>
  </div>
  {f'<div style="margin-top:16px;"><h2 style="margin-bottom:6px;">Vocabulary to Practice</h2>{vocab_html}</div>' if vocab_html else ''}
  <div style="margin-top:16px;background:var(--t-primary-bg);border-radius:14px;padding:14px;">
    <h3 style="color:var(--t-primary);margin-bottom:6px;">Ways to Help at Home</h3>
    <ul style="font-size:12px;color:var(--t-primary-darkest);padding-left:16px;">
      <li>Practice vocabulary words together</li>
      <li>Ask your child to teach you something they learned</li>
      <li>Read together for 20 minutes each night</li>
    </ul>
  </div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_lab_activity(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render science lab activity — objective, hypothesis, materials, procedure, data, analysis."""
    title = content.get("title", "Lab Activity")
    instructions = content.get("instructions", "")
    questions = content.get("questions", [])

    procedure = questions[:5] if len(questions) >= 5 else questions
    analysis = questions[5:] if len(questions) > 5 else []

    steps = "".join(f'<div style="margin-bottom:6px;"><span class="question-number">{i+1}.</span> {q.get("question_text", "")}</div>' for i, q in enumerate(procedure))
    analysis_qs = ""
    for q in analysis:
        if answer_key:
            analysis_qs += f'<div class="question"><span class="question-number">{q.get("question_number", "")}.</span><span class="question-text">{q.get("question_text", "")}</span><div style="margin-left:20px;margin-top:2px;"><span class="answer-key-answer">{q.get("answer", "")}</span></div></div>'
        else:
            analysis_qs += f'<div class="question"><span class="question-number">{q.get("question_number", "")}.</span><span class="question-text">{q.get("question_text", "")}</span><div class="answer-lines-multi"><div class="line"></div><div class="line"></div></div></div>'

    ak = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>{title}{ak}</h1><div class="subtitle">Science Lab</div></div>
    <div class="header-right"><div class="field-line"><span class="field-label">Name:</span><span class="field-blank"></span></div><div class="field-line"><span class="field-label">Date:</span><span class="field-blank"></span></div><div class="field-line"><span class="field-label">Lab Partner:</span><span class="field-blank"></span></div></div>
  </div>
  <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;padding:8px 12px;margin-bottom:12px;font-size:11px;color:#DC2626;">⚠ Safety: Wear goggles. Follow all lab safety rules. Report spills immediately.</div>
  <div style="margin-bottom:12px;"><h2>Objective</h2><p style="font-size:12px;color:var(--t-text-secondary);">{instructions}</p></div>
  <div style="margin-bottom:12px;"><h2>Hypothesis</h2><div style="border-bottom:1px solid var(--t-border);height:24px;"></div><div style="border-bottom:1px solid var(--t-border);height:24px;"></div></div>
  <div style="margin-bottom:12px;"><h2>Procedure</h2>{steps}</div>
  <div style="margin-bottom:12px;"><h2>Data / Observations</h2><div style="border:1px solid var(--t-border);border-radius:10px;min-height:100px;padding:8px;"></div></div>
  <div><h2>Analysis Questions</h2>{analysis_qs}</div>
  <div style="margin-top:12px;"><h2>Conclusion</h2><div class="answer-lines-multi"><div class="line"></div><div class="line"></div><div class="line"></div></div></div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_lab_report(content: dict, config: dict, answer_key: bool = False) -> str:
    """Render formal science lab report template."""
    title = content.get("title", "Lab Report")
    instructions = content.get("instructions", "")
    questions = content.get("questions", [])

    sections = ["Abstract", "Introduction", "Methods", "Results", "Discussion", "Conclusion"]
    section_html = ""
    for sec in sections:
        section_html += f"""
        <div style="margin-bottom:14px;">
          <h2>{sec}</h2>
          <div class="answer-lines-multi">{''.join('<div class="line"></div>' for _ in range(4))}</div>
        </div>"""

    ak = " — Answer Key" if answer_key else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div style="text-align:center;border-bottom:2px solid var(--t-primary);padding-bottom:12px;margin-bottom:16px;">
    <h1 style="font-size:24px;">{title}{ak}</h1>
    <p style="font-size:12px;color:var(--t-text-secondary);">{instructions}</p>
    <div style="margin-top:8px;font-size:11px;color:var(--t-text-muted);">
      Name: _________________ Date: _____________ Period: _____
    </div>
  </div>
  {section_html}
  <div style="margin-top:12px;"><h2>Data Table</h2><div style="border:1px solid var(--t-border);border-radius:10px;min-height:120px;padding:8px;display:flex;align-items:center;justify-content:center;"><span style="font-size:11px;color:var(--t-text-muted);">Record your data here</span></div></div>
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


def render_lesson_plan(plan_data: dict, preset: str = "standard", theme: str = "modern_clean") -> str:
    """Render a lesson plan as HTML. Supports presets: minimal, standard, detailed, full_compliance."""
    global _current_theme
    _current_theme = theme

    rationale = plan_data.get("rationale", "")
    daily_plans = plan_data.get("daily_plans", [])

    days_html = ""
    for dp in daily_plans:
        day = dp.get("day", "").upper()
        title = dp.get("title", "")
        day_date = dp.get("date", "")
        standards = dp.get("standards", [])
        procedures = dp.get("procedures", [])
        work_orders = dp.get("work_orders", [])

        std_badges = "".join(f'<span class="standard-badge">{s}</span>' for s in standards)

        procs_html = ""
        for proc in procedures:
            phase = proc.get("phase", "")
            dur = proc.get("duration_minutes", 0)
            desc = proc.get("description", "")
            proc_stds = proc.get("standards_addressed", [])
            proc_std_html = " ".join(f'<span style="font-size:9px;color:var(--t-primary);font-weight:600;">[{s}]</span>' for s in proc_stds)
            procs_html += f"""
            <div style="display:flex;gap:10px;margin-bottom:8px;padding:6px 0;border-bottom:1px solid var(--t-border-light);">
              <div style="min-width:120px;"><span style="font-weight:600;color:var(--t-primary-darkest);font-size:12px;">{phase}</span><br><span style="font-size:10px;color:var(--t-text-muted);">{dur} min</span></div>
              <div style="flex:1;font-size:12px;color:var(--t-text-secondary);">{desc} {proc_std_html}</div>
            </div>"""

        wo_html = ""
        for wo in work_orders:
            tpl = wo.get("output_template_id", "")
            qc = wo.get("question_count", "")
            wo_html += f'<span style="display:inline-block;background:var(--t-primary-bg);color:var(--t-primary-darkest);font-size:10px;padding:2px 8px;border-radius:4px;margin-right:4px;">{tpl} ({qc}q)</span>'

        days_html += f"""
        <div style="background:white;border-radius:14px;padding:14px;margin-bottom:12px;border:1px solid var(--t-border);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div><span style="font-family:var(--t-heading-font);font-size:16px;color:var(--t-text);">{day} — {title}</span></div>
            <span style="font-size:11px;color:var(--t-text-muted);">{day_date}</span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px;">{std_badges}</div>
          {procs_html}
          <div style="margin-top:6px;">{wo_html}</div>
        </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_base_css()}</head>
<body><div class="page">
  <div class="header"><div class="header-left"><h1>Weekly Lesson Plan</h1><div class="subtitle">{rationale}</div></div></div>
  {days_html}
  <div class="footer">Generated by Lulia AI</div>
</div></body></html>"""


RENDERERS = {
    "worksheet": render_worksheet,
    "task_cards": render_task_cards,
    "exit_ticket": render_exit_ticket,
    "quiz_test": render_quiz_test,
    "flashcards": render_flashcards,
    "bingo": render_bingo,
    "graphic_organizer": render_graphic_organizer,
    "morning_work": render_morning_work,
    "study_guide": render_study_guide,
    "reading_comprehension": render_reading_comprehension,
    "word_search": render_word_search,
    "crossword": render_crossword,
    "board_game": render_board_game,
    "scavenger_hunt": render_scavenger_hunt,
    "escape_room": render_escape_room,
    "vocab_cards": render_vocab_cards,
    "anchor_chart": render_anchor_chart,
    "homework_packet": render_homework_packet,
    "sub_plans": render_sub_plans,
    "parent_newsletter": render_parent_newsletter,
    "lab_activity": render_lab_activity,
    "lab_report": render_lab_report,
}


def render_template(
    template_id: str,
    content: dict,
    answer_key: bool = False,
    theme: str = "modern_clean",
) -> str:
    """
    Render content through a template.

    Args:
        template_id: one of the RENDERERS keys
        content: structured content dict from Content Agent
        answer_key: if True, render the answer key version
        theme: design theme (currently only modern_clean)

    Returns:
        Complete HTML string
    """
    global _current_theme
    _current_theme = theme

    renderer = RENDERERS.get(template_id)
    if not renderer:
        log.warning(f"Unknown template: {template_id}, falling back to worksheet")
        renderer = render_worksheet

    config = get_template_config(template_id)
    return renderer(content, config, answer_key)
