"""
Template Renderer — fills HTML templates with structured content JSON.

Each template in src/lms_agents/templates/{template_id}/ has:
  - template.html: the base HTML with CSS (used as reference only)
  - config.json: parameters like questions_per_page, layout_type, etc.

The renderer builds complete HTML documents from content data using
Python string formatting. Templates are self-contained (inline CSS,
print-ready, no external dependencies).
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
THEMES_DIR = TEMPLATES_DIR / "shared_themes"


def get_template_config(template_id: str) -> dict:
    """Load config.json for a template."""
    config_path = TEMPLATES_DIR / template_id / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


def _base_css(theme: str = "modern_clean") -> str:
    """Shared CSS for all templates — Modern Clean theme."""
    return """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700&display=swap');
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body {
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        color: #1C1917;
        line-height: 1.6;
        background: #fff;
      }
      .page {
        width: 8.5in;
        min-height: 11in;
        padding: 0.6in 0.7in;
        margin: 0 auto;
        position: relative;
      }
      h1, h2, h3 { font-family: 'DM Serif Display', serif; }
      h1 { font-size: 22px; margin-bottom: 4px; }
      h2 { font-size: 16px; margin-bottom: 8px; color: #78350F; }
      h3 { font-size: 13px; margin-bottom: 4px; }
      .header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        border-bottom: 2px solid #F97316;
        padding-bottom: 10px;
        margin-bottom: 16px;
      }
      .header-left h1 { color: #1C1917; }
      .header-left .subtitle { font-size: 12px; color: #78716C; margin-top: 2px; }
      .header-right {
        text-align: right;
        font-size: 12px;
        color: #78716C;
      }
      .header-right .field-line {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 4px;
        justify-content: flex-end;
      }
      .header-right .field-label { font-weight: 600; color: #78350F; font-size: 11px; }
      .header-right .field-blank {
        border-bottom: 1px solid #E7E5E4;
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
        background: #FFF7ED;
        color: #9A3412;
        border: 1px solid #FDBA74;
        font-weight: 500;
      }
      .instructions {
        background: #FFF7ED;
        border-left: 3px solid #F97316;
        padding: 8px 12px;
        font-size: 12px;
        color: #78350F;
        margin-bottom: 16px;
        border-radius: 0 8px 8px 0;
      }
      .question {
        margin-bottom: 14px;
        page-break-inside: avoid;
      }
      .question-number {
        font-weight: 700;
        color: #F97316;
        margin-right: 6px;
      }
      .question-text { font-size: 13px; color: #1C1917; }
      .answer-line {
        border-bottom: 1px solid #E7E5E4;
        height: 24px;
        margin-top: 6px;
        margin-left: 20px;
      }
      .answer-lines-multi {
        margin-top: 6px;
        margin-left: 20px;
      }
      .answer-lines-multi .line {
        border-bottom: 1px solid #E7E5E4;
        height: 22px;
      }
      .mc-options {
        margin-top: 4px;
        margin-left: 20px;
        font-size: 13px;
      }
      .mc-options .option { margin-bottom: 2px; }
      .mc-options .option-letter { font-weight: 600; color: #78350F; margin-right: 8px; }
      .word-bank {
        border: 1px solid #E7E5E4;
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 16px;
        background: #FEF9F2;
      }
      .word-bank-title { font-size: 11px; font-weight: 600; color: #78350F; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
      .word-bank-words { display: flex; flex-wrap: wrap; gap: 8px; }
      .word-bank-word { font-size: 13px; color: #1C1917; padding: 2px 10px; background: white; border-radius: 6px; border: 1px solid #FDBA74; }
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
      .points { font-size: 10px; color: #A8A29E; float: right; }
      .answer-key-answer { color: #16A34A; font-weight: 600; }
      .footer {
        position: absolute;
        bottom: 0.4in;
        left: 0.7in;
        right: 0.7in;
        text-align: center;
        font-size: 9px;
        color: #A8A29E;
        border-top: 1px solid #F5F5F4;
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
        border: 1px solid #E7E5E4;
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
        color: #F97316;
        background: #FFF7ED;
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
        border: 2px solid #F97316;
        border-radius: 10px;
        overflow: hidden;
      }
      .bingo-cell {
        border: 1px solid #E7E5E4;
        padding: 10px 4px;
        text-align: center;
        font-size: 11px;
        min-height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .bingo-header {
        background: #F97316;
        color: white;
        font-family: 'DM Serif Display', serif;
        font-size: 18px;
        font-weight: 700;
        padding: 8px;
      }
      .bingo-free {
        background: #FFF7ED;
        font-weight: 700;
        color: #F97316;
        font-size: 14px;
      }
      /* Passage */
      .passage {
        background: #FEF9F2;
        border: 1px solid #E7E5E4;
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
        color: #A8A29E;
        font-size: 10px;
        user-select: none;
      }
      .vocab-sidebar {
        background: #FFF7ED;
        border-radius: 10px;
        padding: 12px;
        font-size: 12px;
      }
      .vocab-sidebar .vocab-word { font-weight: 600; color: #78350F; }
      .vocab-sidebar .vocab-def { color: #78716C; margin-left: 4px; }
      /* Two-column for reading comp */
      .two-col { display: grid; grid-template-columns: 1fr 200px; gap: 16px; }
      /* Half-page */
      .half-page { min-height: 5.25in; max-height: 5.5in; overflow: hidden; }
      .half-divider { border-top: 2px dashed #E7E5E4; margin: 8px 0; }
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
        border: 2px solid #F97316;
        border-radius: 10px;
        overflow: hidden;
      }
      .go-tchart-header {
        background: #FFF7ED;
        padding: 8px;
        font-weight: 600;
        text-align: center;
        border-bottom: 2px solid #F97316;
        font-family: 'DM Serif Display', serif;
      }
      .go-tchart-cell {
        padding: 12px;
        min-height: 200px;
        border-right: 1px solid #E7E5E4;
      }
      .go-kwl {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        border: 2px solid #F97316;
        border-radius: 10px;
        overflow: hidden;
      }
      .study-topic {
        background: #FFF7ED;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
      }
      .study-vocab { font-weight: 600; color: #F97316; }
      .study-example {
        background: #FEF9F2;
        border-left: 3px solid #FDBA74;
        padding: 8px 12px;
        margin: 8px 0;
        font-size: 12px;
        border-radius: 0 8px 8px 0;
      }
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

        answer_html = ""
        if answer_key:
            ans = q.get("answer", "")
            answer_html = f'<div style="margin-top:4px;margin-left:20px;"><span class="answer-key-answer">{ans}</span></div>'
        else:
            answer_html = '<div class="answer-line"></div>'

        questions_html += f"""
        <div class="question">
          <div><span class="question-number">{num}.</span><span class="question-text">{text}</span>{diff_badge}{pts_html}</div>
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
        if answer_key:
            ans = q.get("answer", "")
            cards_html += f"""
            <div class="card">
              <div class="card-number">{num}</div>
              <div class="question-text" style="margin-bottom:8px;">{text}</div>
              <div class="answer-key-answer">{ans}</div>
            </div>"""
        else:
            cards_html += f"""
            <div class="card">
              <div class="card-number">{num}</div>
              <div class="question-text" style="padding-right:20px;">{text}</div>
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
            if is_answer:
                ans = q.get("answer", "")
                qs += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span><div style="margin-left:20px;margin-top:2px;"><span class="answer-key-answer">{ans}</span></div></div>'
            else:
                qs += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span><div class="answer-line"></div></div>'
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

        if answer_key:
            ans = q.get("answer", "")
            answer_html = f'<div style="margin-top:4px;margin-left:20px;"><span class="answer-key-answer">{ans}</span></div>'
        else:
            answer_html = '<div class="answer-lines-multi"><div class="line"></div><div class="line"></div></div>'

        questions_html += f"""
        <div class="question">
          <div><span class="question-number">{num}.</span><span class="question-text">{text}</span>{pts_html}</div>
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
        if answer_key:
            ans = q.get("answer", "")
            qs_html += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span><div style="margin-left:20px;margin-top:2px;"><span class="answer-key-answer">{ans}</span></div></div>'
        else:
            qs_html += f'<div class="question"><span class="question-number">{num}.</span><span class="question-text">{text}</span><div class="answer-line"></div></div>'

    challenge_html = ""
    if challenge:
        ch_text = challenge.get("question_text", "")
        if answer_key:
            ch_ans = challenge.get("answer", "")
            challenge_html = f'<div style="background:#FFF7ED;border:2px solid #F97316;border-radius:10px;padding:12px;margin-top:12px;"><h3 style="color:#F97316;margin-bottom:4px;">Challenge</h3><div class="question-text">{ch_text}</div><div style="margin-top:4px;"><span class="answer-key-answer">{ch_ans}</span></div></div>'
        else:
            challenge_html = f'<div style="background:#FFF7ED;border:2px solid #F97316;border-radius:10px;padding:12px;margin-top:12px;"><h3 style="color:#F97316;margin-bottom:4px;">Challenge</h3><div class="question-text">{ch_text}</div><div class="answer-line"></div></div>'

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
    renderer = RENDERERS.get(template_id)
    if not renderer:
        log.warning(f"Unknown template: {template_id}, falling back to worksheet")
        renderer = render_worksheet

    config = get_template_config(template_id)
    return renderer(content, config, answer_key)
