"""
Interactive Activity Generator — creates self-contained HTML activities
that students access via a link. No build step needed — React loads via CDN.

Each activity is a single HTML file with embedded content data that runs
a React component for the selected interaction type.
"""
import json
import logging
import os
import random
import string
from uuid import uuid4

import boto3
from psycopg2.extras import Json

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

INTERACTIVE_TEMPLATES = {
    "multiple_choice_quiz": {"name": "Multiple Choice Quiz", "group": "Quiz", "desc": "Click-to-answer with instant feedback"},
    "drag_drop_sort": {"name": "Drag & Drop Sort", "group": "Drag-Drop", "desc": "Drag items into categories"},
    "drag_drop_sequence": {"name": "Sequence Order", "group": "Drag-Drop", "desc": "Drag items into correct order"},
    "matching_pairs": {"name": "Matching Pairs", "group": "Matching", "desc": "Match items in two columns"},
    "fill_in_blank": {"name": "Fill in the Blank", "group": "Text", "desc": "Click word bank or type answer"},
    "click_to_reveal": {"name": "Click to Reveal", "group": "Study", "desc": "Click cards to reveal answers"},
    "flash_cards_interactive": {"name": "Flashcards", "group": "Study", "desc": "Swipe to flip cards"},
    "category_sort": {"name": "Category Sort", "group": "Drag-Drop", "desc": "Drop items into buckets"},
    "word_search_interactive": {"name": "Word Search", "group": "Puzzle", "desc": "Find hidden words"},
    "crossword_interactive": {"name": "Crossword", "group": "Puzzle", "desc": "Type answers into grid"},
    "number_line": {"name": "Number Line", "group": "Math", "desc": "Place values on number line"},
    "slider_estimation": {"name": "Estimation Slider", "group": "Math", "desc": "Slide to estimate values"},
    "timeline_builder": {"name": "Timeline Builder", "group": "Social Studies", "desc": "Drag events chronologically"},
    "whiteboard_response": {"name": "Whiteboard Response", "group": "Open", "desc": "Free-text or drawing"},
    "hotspot_labeling": {"name": "Hotspot Labeling", "group": "Science", "desc": "Click to label parts"},
}


def _generate_access_code() -> str:
    """Generate a 6-char access code like BEAR23."""
    words = ["BEAR", "LION", "STAR", "MOON", "TREE", "FISH", "BIRD", "FROG", "LEAF", "WAVE"]
    return random.choice(words) + "".join(random.choices(string.digits, k=2))


def _strip_bracketed_visual_refs(text: str) -> str:
    """
    Remove bracketed visual placeholder text that occasionally leaks past the
    QA Agent's filter. Covers phrasings like '[Visual shows ...]', '[Image:
    water cycle]', '[Diagram of cell]'. Keeps the surrounding question stem
    intact so the student can still answer.
    """
    if not isinstance(text, str):
        return text
    import re as _re
    return _re.sub(
        r"\[(?:image|picture|diagram|illustration|graphic|visual|drawing|figure|photo|chart)[^\]]*\]",
        "",
        text,
        flags=_re.IGNORECASE,
    ).replace("  ", " ").strip()


def _clean_content_for_activity(content: dict) -> dict:
    """
    Pre-process content before embedding in the activity HTML:
    - Strip [Visual ...] placeholder text from question stems
    - Pre-render structured `visual` objects to inline SVG/HTML so the
      React template can show them via dangerouslySetInnerHTML. Python
      stays the single source of truth for the 19 canonical visual types
      (ten_frame, number_bond, fraction_bar, array, bar_model, area_model,
      number_line, coordinate_grid, function_table, equation_box,
      base_ten_blocks, counting_objects, data_table, labeled_diagram,
      letter_box, word_box, handwriting_lines, picture_choice, plus any
      registered additions).
    """
    from src.lms_agents.tools.visual_renderer import render_visual

    questions = content.get("questions", [])
    cleaned = []
    for q in questions:
        q_copy = dict(q) if isinstance(q, dict) else {}
        if "question_text" in q_copy:
            q_copy["question_text"] = _strip_bracketed_visual_refs(q_copy["question_text"])
        # Pre-render the structured `visual` (if any) to an HTML string.
        # Renderer returns empty string when visual is missing or malformed.
        for src_key, dst_key in (("visual", "visual_html"), ("answer_visual", "answer_visual_html")):
            v = q_copy.get(src_key)
            if v:
                try:
                    svg_html = render_visual(v)
                    if svg_html:
                        q_copy[dst_key] = svg_html
                except Exception as e:
                    log.warning(f"[Interactive] {src_key} render failed: {e}")
        cleaned.append(q_copy)
    out = dict(content)
    out["questions"] = cleaned
    return out


def _build_activity_html(template_id: str, content: dict, activity_id: str, api_url: str) -> str:
    """
    Build a self-contained HTML file for the interactive activity.
    Uses React via CDN — no build step needed.
    """
    from src.lms_agents.tools.visual_renderer import get_visual_css

    content = _clean_content_for_activity(content)
    title = content.get("title", "Activity")
    questions = content.get("questions", [])
    instructions = content.get("instructions", "")

    # Serialize content for embedding
    content_json = json.dumps(content)
    # CSS for structured visuals — uses CSS variable fallbacks so it inherits
    # whatever colors the activity shell defines. Kept separate so the
    # visual_renderer is the single source of truth.
    visual_css = get_visual_css()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Lulia</title>
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'DM Sans', sans-serif; background: #F5DEC3; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px; }}
.app {{ max-width: 680px; width: 100%; background: #FEF9F2; border-radius: 20px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
h1 {{ font-family: 'DM Serif Display', serif; color: #1C1917; font-size: 22px; margin-bottom: 4px; }}
h2 {{ font-family: 'DM Serif Display', serif; color: #78350F; font-size: 16px; margin-bottom: 12px; }}
.subtitle {{ font-size: 13px; color: #78716C; margin-bottom: 16px; }}
.btn-primary {{ background: #F97316; color: white; border: none; padding: 12px 24px; border-radius: 12px; font-size: 14px; font-weight: 600; cursor: pointer; width: 100%; font-family: 'DM Sans'; }}
.btn-primary:hover {{ background: #EA580C; }}
.btn-primary:disabled {{ background: #FDBA74; cursor: not-allowed; }}
.btn-secondary {{ background: white; color: #78350F; border: 1px solid #E7E5E4; padding: 10px 20px; border-radius: 12px; font-size: 13px; font-weight: 500; cursor: pointer; font-family: 'DM Sans'; }}
.input {{ width: 100%; border: 1px solid #E7E5E4; border-radius: 12px; padding: 12px 16px; font-size: 14px; outline: none; font-family: 'DM Sans'; }}
.input:focus {{ border-color: #F97316; box-shadow: 0 0 0 3px rgba(249,115,22,0.1); }}
.question-card {{ background: white; border-radius: 14px; padding: 16px; margin-bottom: 12px; }}
.option {{ display: block; width: 100%; text-align: left; padding: 12px 16px; border: 2px solid #E7E5E4; border-radius: 10px; margin-bottom: 8px; cursor: pointer; font-size: 14px; font-family: 'DM Sans'; background: white; transition: all 0.2s; }}
.option:hover {{ border-color: #FDBA74; background: #FFF7ED; }}
.option.selected {{ border-color: #F97316; background: #FFF7ED; }}
.option.correct {{ border-color: #22C55E; background: #DCFCE7; }}
.option.wrong {{ border-color: #EF4444; background: #FEF2F2; }}
.feedback {{ padding: 8px 12px; border-radius: 8px; font-size: 13px; margin-top: 8px; }}
.feedback.correct {{ background: #DCFCE7; color: #16A34A; }}
.feedback.wrong {{ background: #FEF2F2; color: #EF4444; }}
.progress {{ height: 6px; background: #E7E5E4; border-radius: 3px; margin-bottom: 16px; overflow: hidden; }}
.progress-bar {{ height: 100%; background: #F97316; border-radius: 3px; transition: width 0.3s; }}
.score-card {{ text-align: center; padding: 24px; }}
.score-big {{ font-size: 48px; font-weight: 700; color: #F97316; }}
.score-label {{ font-size: 14px; color: #78716C; }}
.badge {{ display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #FFF7ED; color: #9A3412; border: 1px solid #FDBA74; margin: 2px; }}
.logo {{ text-align: center; font-size: 11px; color: #A8A29E; margin-top: 16px; }}
.drag-item {{ padding: 10px 16px; background: white; border: 2px solid #E7E5E4; border-radius: 10px; margin: 4px; cursor: grab; font-size: 13px; display: inline-block; }}
.drag-item:active {{ cursor: grabbing; }}
.drop-zone {{ min-height: 60px; border: 2px dashed #FDBA74; border-radius: 12px; padding: 8px; margin-bottom: 8px; }}
.drop-zone.over {{ background: #FFF7ED; border-color: #F97316; }}
.match-col {{ display: flex; flex-direction: column; gap: 8px; }}
.match-item {{ padding: 10px; border: 2px solid #E7E5E4; border-radius: 10px; cursor: pointer; text-align: center; font-size: 13px; transition: all 0.2s; }}
.match-item.active {{ border-color: #F97316; background: #FFF7ED; }}
.match-item.matched {{ border-color: #22C55E; background: #DCFCE7; cursor: default; }}
.match-item.wrong {{ border-color: #EF4444; background: #FEF2F2; animation: shake 0.4s; }}
@keyframes shake {{ 0%, 100% {{ transform: translateX(0); }} 25% {{ transform: translateX(-4px); }} 75% {{ transform: translateX(4px); }} }}
.flip-card {{ perspective: 1000px; cursor: pointer; }}
.flip-inner {{ transition: transform 0.5s; transform-style: preserve-3d; position: relative; min-height: 120px; }}
.flip-card.flipped .flip-inner {{ transform: rotateY(180deg); }}
.flip-front, .flip-back {{ position: absolute; width: 100%; backface-visibility: hidden; border-radius: 14px; padding: 20px; display: flex; align-items: center; justify-content: center; text-align: center; }}
.flip-front {{ background: white; border: 2px solid #E7E5E4; }}
.flip-back {{ background: #FFF7ED; border: 2px solid #F97316; transform: rotateY(180deg); }}

/* ── Structured visuals (ten_frame, number_bond, fraction_bar, etc.) ── */
/* Inlined from visual_renderer.get_visual_css() so interactive activities
   render visuals the same way worksheets do. */
{visual_css}
</style>
</head>
<body>
<div id="root"></div>
<script>
window.LULIA_DATA = {content_json};
window.LULIA_ACTIVITY_ID = "{activity_id}";
window.LULIA_API = "{api_url}";
window.LULIA_TEMPLATE = "{template_id}";
</script>
<script type="text/babel">
const {{ useState, useEffect }} = React;
const data = window.LULIA_DATA;
const activityId = window.LULIA_ACTIVITY_ID;
const apiUrl = window.LULIA_API;

function App() {{
  const [screen, setScreen] = useState('welcome');
  const [name, setName] = useState('');
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState({{}});
  const [score, setScore] = useState(null);
  const [startTime] = useState(Date.now());
  const questions = data.questions || [];

  function handleAnswer(qNum, answer) {{
    setAnswers(prev => ({{...prev, [qNum]: answer}}));
  }}

  function submitAll() {{
    let correct = 0;
    questions.forEach(q => {{
      const resp = answers[q.question_number];
      if (resp && resp.toLowerCase().trim() === (q.answer || '').toLowerCase().trim()) correct++;
    }});
    const pct = Math.round(correct / Math.max(questions.length, 1) * 100);
    setScore({{ correct, total: questions.length, percentage: pct }});
    setScreen('results');
    // POST to API
    fetch(apiUrl + '/api/v1/interactive/' + activityId + '/submit', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        student_name: name,
        responses: answers,
        time_spent: Math.round((Date.now() - startTime) / 1000),
      }}),
    }}).catch(() => {{}});
  }}

  if (screen === 'welcome') return (
    <div className="app">
      <h1>{{data.title}}</h1>
      <p className="subtitle">{{data.instructions || `${{questions.length}} questions`}}</p>
      <div style={{{{marginBottom: 16}}}}>
        <input className="input" placeholder="Enter your name" value={{name}} onChange={{e => setName(e.target.value)}} />
      </div>
      <button className="btn-primary" disabled={{!name.trim()}} onClick={{() => setScreen('play')}}>Start Activity</button>
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );

  if (screen === 'results') return (
    <div className="app">
      <div className="score-card">
        <h2>Great work, {{name}}!</h2>
        <div className="score-big">{{score.percentage}}%</div>
        <div className="score-label">{{score.correct}} of {{score.total}} correct</div>
        <div style={{{{marginTop: 16}}}}>
          {{(data.questions || []).map(q => (
            <span key={{q.question_number}} className="badge" style={{{{
              background: answers[q.question_number]?.toLowerCase().trim() === q.answer?.toLowerCase().trim() ? '#DCFCE7' : '#FEF2F2',
              color: answers[q.question_number]?.toLowerCase().trim() === q.answer?.toLowerCase().trim() ? '#16A34A' : '#EF4444',
              borderColor: answers[q.question_number]?.toLowerCase().trim() === q.answer?.toLowerCase().trim() ? '#22C55E' : '#EF4444',
            }}}}>
              Q{{q.question_number}}: {{answers[q.question_number]?.toLowerCase().trim() === q.answer?.toLowerCase().trim() ? '✓' : '✗'}}
            </span>
          ))}}
        </div>
      </div>
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );

  // ── Play screen dispatch ──────────────────────────────────────────────
  // Each template type gets its own renderer. MCQ is the fallback for
  // types that haven't been specialized yet (keeps them working).
  const template = window.LULIA_TEMPLATE || 'multiple_choice_quiz';

  function finishWithScore(s) {{
    setScore(s);
    setScreen('results');
    fetch(apiUrl + '/api/v1/interactive/' + activityId + '/submit', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        student_name: name,
        responses: s.responses || {{}},
        time_spent: Math.round((Date.now() - startTime) / 1000),
      }}),
    }}).catch(() => {{}});
  }}

  if (template === 'matching_pairs') {{
    return <PlayMatchingPairs data={{data}} name={{name}} onComplete={{finishWithScore}} />;
  }}

  // ── MCQ (fallback for all other templates until specialized) ─────────
  const q = questions[current];
  const progress = ((current + 1) / questions.length) * 100;
  return (
    <div className="app">
      <div className="progress"><div className="progress-bar" style={{{{width: progress + '%'}}}} /></div>
      <div style={{{{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}}}>
        <span style={{{{fontSize: 12, color: '#A8A29E'}}}}>Question {{current + 1}} of {{questions.length}}</span>
        <span style={{{{fontSize: 12, color: '#A8A29E'}}}}>{{name}}</span>
      </div>
      <div className="question-card">
        <h2>{{q?.question_text}}</h2>
        {{q?.visual_html && (
          <div dangerouslySetInnerHTML={{{{ __html: q.visual_html }}}} />
        )}}
        {{Array.isArray(q?.options) && q.options.length >= 2 ? (
          ['A', 'B', 'C', 'D'].slice(0, q.options.length).map((letter, i) => {{
            const optionText = q.options[i];
            const selected = answers[q?.question_number] === optionText;
            return (
              <button key={{letter}} className={{`option ${{selected ? 'selected' : ''}}`}}
                onClick={{() => handleAnswer(q.question_number, optionText)}}>
                <strong>{{letter}}.</strong> {{optionText}}
              </button>
            );
          }})
        ) : (
          <input className="input" placeholder="Type your answer..." autoFocus
            value={{answers[q?.question_number] || ''}}
            onChange={{e => handleAnswer(q?.question_number, e.target.value)}} />
        )}}
      </div>
      <div style={{{{display: 'flex', gap: 8}}}}>
        {{current > 0 && <button className="btn-secondary" onClick={{() => setCurrent(c => c - 1)}}>Back</button>}}
        {{current < questions.length - 1 ? (
          <button className="btn-primary" onClick={{() => setCurrent(c => c + 1)}}>Next</button>
        ) : (
          <button className="btn-primary" onClick={{submitAll}}>Submit</button>
        )}}
      </div>
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );
}}

// ── Matching Pairs renderer ────────────────────────────────────────────
// Content shape: uses the same questions[] — each entry becomes a pair
// where question_text is the left side and answer is the right side.
// Either side can carry an optional structured visual which was
// pre-rendered to visual_html / answer_visual_html at build time.
function PlayMatchingPairs({{ data, name, onComplete }}) {{
  const allPairs = (data.questions || []).map((q, i) => ({{
    id: q.question_number || i,
    left: q.question_text || '',
    leftHtml: q.visual_html || null,
    right: q.answer || '',
    rightHtml: q.answer_visual_html || null,
  }}));

  // Shuffled columns
  const [leftOrder] = useState(() => allPairs.map(p => p.id).sort(() => Math.random() - 0.5));
  const [rightOrder] = useState(() => allPairs.map(p => p.id).sort(() => Math.random() - 0.5));
  const pairById = Object.fromEntries(allPairs.map(p => [p.id, p]));

  const [selectedLeft, setSelectedLeft] = useState(null);
  const [selectedRight, setSelectedRight] = useState(null);
  const [matched, setMatched] = useState(new Set());
  const [wrongFlash, setWrongFlash] = useState(null);
  const [attempts, setAttempts] = useState(0);
  const [correctHits, setCorrectHits] = useState(0);

  function tryMatch(leftId, rightId) {{
    setAttempts(a => a + 1);
    if (leftId === rightId) {{
      setCorrectHits(h => h + 1);
      const next = new Set(matched);
      next.add(leftId);
      setMatched(next);
      setSelectedLeft(null);
      setSelectedRight(null);
      if (next.size === allPairs.length) {{
        setTimeout(() => onComplete({{
          correct: next.size,
          total: allPairs.length,
          percentage: Math.round((next.size / allPairs.length) * 100),
          attempts: attempts + 1,
          accuracy: Math.round(((correctHits + 1) / (attempts + 1)) * 100),
          responses: {{}},
        }}), 400);
      }}
    }} else {{
      setWrongFlash({{ left: leftId, right: rightId }});
      setTimeout(() => {{
        setWrongFlash(null);
        setSelectedLeft(null);
        setSelectedRight(null);
      }}, 500);
    }}
  }}

  function clickLeft(id) {{
    if (matched.has(id)) return;
    setSelectedLeft(id);
    if (selectedRight !== null) tryMatch(id, selectedRight);
  }}
  function clickRight(id) {{
    if (matched.has(id)) return;
    setSelectedRight(id);
    if (selectedLeft !== null) tryMatch(selectedLeft, id);
  }}

  function tileClass(id, side) {{
    const isSel = side === 'L' ? selectedLeft === id : selectedRight === id;
    const isMatched = matched.has(id);
    const isWrong = wrongFlash && (side === 'L' ? wrongFlash.left === id : wrongFlash.right === id);
    if (isMatched) return 'match-item matched';
    if (isWrong) return 'match-item wrong';
    if (isSel) return 'match-item active';
    return 'match-item';
  }}

  const progress = Math.round((matched.size / Math.max(allPairs.length, 1)) * 100);
  return (
    <div className="app">
      <div className="progress"><div className="progress-bar" style={{{{width: progress + '%'}}}} /></div>
      <div style={{{{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}}}>
        <span style={{{{fontSize: 12, color: '#A8A29E'}}}}>Matched {{matched.size}} of {{allPairs.length}}</span>
        <span style={{{{fontSize: 12, color: '#A8A29E'}}}}>{{name}}</span>
      </div>
      <h2 style={{{{marginBottom: 12}}}}>{{data.title || 'Matching Pairs'}}</h2>
      {{data.instructions && <p className="subtitle">{{data.instructions}}</p>}}
      <div style={{{{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12}}}}>
        <div className="match-col">
          {{leftOrder.map(id => {{
            const p = pairById[id];
            return (
              <div key={{'L' + id}} className={{tileClass(id, 'L')}} onClick={{() => clickLeft(id)}}>
                {{p.leftHtml
                  ? <div dangerouslySetInnerHTML={{{{ __html: p.leftHtml }}}} />
                  : <span>{{p.left}}</span>}}
              </div>
            );
          }})}}
        </div>
        <div className="match-col">
          {{rightOrder.map(id => {{
            const p = pairById[id];
            return (
              <div key={{'R' + id}} className={{tileClass(id, 'R')}} onClick={{() => clickRight(id)}}>
                {{p.rightHtml
                  ? <div dangerouslySetInnerHTML={{{{ __html: p.rightHtml }}}} />
                  : <span>{{p.right}}</span>}}
              </div>
            );
          }})}}
        </div>
      </div>
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );
}}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
</script>
</body>
</html>"""


def generate_interactive_activity(
    assignment_id: str,
    teacher_id: str,
    interactive_template_id: str = "multiple_choice_quiz",
    class_id: str | None = None,
    max_attempts: int = 3,
    show_answers_after: bool = True,
    time_limit: int | None = None,
) -> dict:
    """
    Generate and deploy an interactive activity.
    Returns activity_id, access_code, and access_url.
    """
    log.info(f"[Interactive] Generating {interactive_template_id} for assignment {assignment_id}")

    # Get assignment content
    conn = get_connection()
    from psycopg2.extras import RealDictCursor
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM assignments WHERE assignment_id = %s", (assignment_id,))
    assignment = cur.fetchone()
    cur.close()
    conn.close()

    if not assignment:
        return {"error": "Assignment not found"}

    content = {
        "title": assignment["title"],
        "instructions": "",
        "questions": assignment["questions"] if isinstance(assignment["questions"], list) else [],
        "standards": assignment.get("standards_ids", []),
    }

    activity_id = str(uuid4())
    access_code = _generate_access_code()
    api_url = os.environ.get("API_URL", "http://localhost:8000")

    # Build the HTML
    html = _build_activity_html(interactive_template_id, content, activity_id, api_url)

    # Deploy to MinIO
    access_url = None
    try:
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        key = f"activities/{activity_id}/index.html"
        s3.put_object(
            Bucket=os.environ.get("S3_BUCKET_ACTIVITIES", "lulia-activities"),
            Key=key,
            Body=html.encode(),
            ContentType="text/html",
        )
        # Browser-facing URL MUST use the public endpoint (localhost:9000 in
        # dev, CloudFront/S3 domain in prod). S3_ENDPOINT is the Docker-internal
        # hostname that only boto3 inside the api container can resolve.
        endpoint = os.environ.get("S3_PUBLIC_ENDPOINT") or os.environ.get("S3_ENDPOINT", "http://localhost:9000")
        access_url = f"{endpoint}/lulia-activities/{key}"
        log.info(f"[Interactive] Deployed to {access_url}")
    except Exception as e:
        log.error(f"[Interactive] Deploy failed: {e}")
        access_url = f"/activities/{activity_id}"

    # Store in DB
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO interactive_activities
               (activity_id, assignment_id, teacher_id, class_id,
                interactive_template_id, content_json, access_code, access_url,
                max_attempts, time_limit_seconds, show_answers_after, status)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'live')""",
            (activity_id, assignment_id, teacher_id, class_id,
             interactive_template_id, Json(content), access_code, access_url,
             max_attempts, time_limit, show_answers_after),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"[Interactive] DB insert failed: {e}")
    finally:
        cur.close()
        conn.close()

    return {
        "activity_id": activity_id,
        "access_code": access_code,
        "access_url": access_url,
        "template": interactive_template_id,
        "question_count": len(content["questions"]),
        "status": "live",
    }


# ---------------------------------------------------------------------------
# Refinement (Pattern C — post-generation chips)
# ---------------------------------------------------------------------------
# Given an existing activity and a refinement instruction, produce a NEW
# activity with the refinement applied. Preserves the original for
# before/after comparison. Uses Claude Sonnet to rewrite content_json.

REFINE_INSTRUCTIONS = {
    "make_harder":         "Increase cognitive demand. Add application or multi-step reasoning, use more precise vocabulary, and make distractors (if any) harder to eliminate.",
    "simpler_vocabulary":  "Use simpler words — aim for 1-2 grade levels below the listed grade. Shorten sentences. Keep the same concept.",
    "trickier_distractors":"Keep the same questions, but replace wrong-answer distractors with common misconceptions students at this grade actually have.",
    "add_visuals":         "Where natural, add structured visual elements (fraction bars, number lines, ten-frames, labeled diagrams) inline with the questions. Use the structured `visual` field, not bracketed text.",
    "different_examples":  "Keep the same topic and difficulty, but swap every specific example for a fresh one. Do not reuse any numbers, names, or wording from the original.",
    "more_items":          "Increase the item count by 50%. Maintain the current difficulty distribution.",
    "fewer_items":         "Reduce to the strongest 60% of items. Drop the weakest — keep the ones that best assess the objective.",
    "more_clues":          "Increase the number of words or clues by 50%. Maintain difficulty.",
    "simpler_clues":       "Rewrite the clues to use simpler vocabulary and shorter phrasing. Keep the same answer words.",
    "picture_clues":       "Where applicable, add a structured visual to each clue so students can answer from a picture as well as the text.",
    "more_pairs":          "Add 50% more pairs, keeping the same pair-type relationship.",
    "visual_cues":         "Add a small structured visual alongside each pair so the relationship is visible, not just readable.",
    "trickier_matches":    "Keep the same topic, but pick pairs where the relationship is less obvious — students must actually think, not just pattern-match.",
    "simpler_pairs":       "Replace pairs with more familiar, high-frequency examples at a grade level below the listed grade.",
    "more_labels":         "Increase the number of hotspots/labels by 50%. Cover more parts of the diagram.",
    "different_diagram":   "Swap the diagram for a different image covering the same concept (e.g. different cell type, different map region).",
}


def refine_activity(
    activity_id: str,
    instruction_id: str,
    custom_instructions: str | None = None,
) -> dict:
    """
    Produce a refined copy of an existing activity. Creates a NEW activity row
    so the original is preserved for before/after comparison.

    Args:
        activity_id: the activity to refine (source)
        instruction_id: one of the keys in REFINE_INSTRUCTIONS, or "custom"
        custom_instructions: free-form text when instruction_id == "custom"

    Returns: same shape as generate_interactive_activity()
    """
    import anthropic
    from psycopg2.extras import RealDictCursor

    instruction_text = REFINE_INSTRUCTIONS.get(instruction_id)
    if instruction_id == "custom":
        instruction_text = (custom_instructions or "").strip()
    if not instruction_text:
        return {"error": f"Unknown refinement instruction: {instruction_id}"}

    # Load existing activity
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM interactive_activities WHERE activity_id = %s",
        (activity_id,),
    )
    original = cur.fetchone()
    cur.close(); conn.close()
    if not original:
        return {"error": "Activity not found"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}

    template_id = original["interactive_template_id"]
    original_content = original["content_json"]

    prompt = (
        f"You are refining an interactive {template_id} activity based on teacher feedback.\n\n"
        f"ORIGINAL CONTENT JSON:\n{json.dumps(original_content, indent=2)}\n\n"
        f"TEACHER REFINEMENT REQUEST:\n{instruction_text}\n\n"
        f"Produce the refined content JSON in EXACTLY the same schema as the original. "
        f"Preserve the overall topic and activity type. Only change what the refinement "
        f"request asks you to change. Return ONLY valid JSON — no preamble, no markdown."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.content[0].text or "").strip()
        import re as _re
        match = _re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {"error": "Sonnet did not return valid JSON"}
        new_content = json.loads(match.group())
    except Exception as e:
        log.error(f"[Refine] Sonnet call failed: {e}")
        return {"error": f"Refinement failed: {e}"}

    # Deploy refined activity as a NEW row + new HTML upload
    new_activity_id = str(uuid4())
    new_access_code = _generate_access_code()
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    html = _build_activity_html(template_id, new_content, new_activity_id, api_url)

    access_url = None
    try:
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        key = f"activities/{new_activity_id}/index.html"
        s3.put_object(
            Bucket=os.environ.get("S3_BUCKET_ACTIVITIES", "lulia-activities"),
            Key=key,
            Body=html.encode(),
            ContentType="text/html",
        )
        endpoint = os.environ.get("S3_PUBLIC_ENDPOINT") or os.environ.get("S3_ENDPOINT", "http://localhost:9000")
        access_url = f"{endpoint}/lulia-activities/{key}"
    except Exception as e:
        log.error(f"[Refine] Deploy failed: {e}")
        access_url = f"/activities/{new_activity_id}"

    # Insert new row linked back to the original via content_json metadata
    conn = get_connection()
    cur = conn.cursor()
    try:
        new_content["_refined_from"] = activity_id
        new_content["_refinement_instruction"] = instruction_id
        cur.execute(
            """INSERT INTO interactive_activities
               (activity_id, assignment_id, teacher_id, class_id,
                interactive_template_id, content_json, access_code, access_url,
                max_attempts, time_limit_seconds, show_answers_after, status)
               VALUES (%s, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'live')""",
            (new_activity_id, original["assignment_id"], original["teacher_id"], original["class_id"],
             template_id, Json(new_content), new_access_code, access_url,
             original["max_attempts"], original["time_limit_seconds"], original["show_answers_after"]),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"[Refine] DB insert failed: {e}")
        return {"error": f"DB insert failed: {e}"}
    finally:
        cur.close(); conn.close()

    return {
        "activity_id": new_activity_id,
        "access_code": new_access_code,
        "access_url": access_url,
        "template": template_id,
        "refined_from": activity_id,
        "instruction_id": instruction_id,
        "status": "live",
    }


def submit_interactive_response(
    activity_id: str,
    student_name: str,
    responses: dict,
    time_spent: int = 0,
) -> dict:
    """Process and store a student's interactive submission."""
    conn = get_connection()
    from psycopg2.extras import RealDictCursor
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM interactive_activities WHERE activity_id = %s", (activity_id,))
    activity = cur.fetchone()
    cur.close()

    if not activity:
        conn.close()
        return {"error": "Activity not found"}

    content = activity["content_json"]
    questions = content.get("questions", [])

    # Grade responses
    correct = 0
    max_score = len(questions)
    standards_mastery = {}

    for q in questions:
        qnum = q.get("question_number", 0)
        correct_answer = (q.get("answer", "") or "").lower().strip()
        student_resp = (str(responses.get(str(qnum), responses.get(qnum, ""))) or "").lower().strip()

        is_correct = student_resp == correct_answer
        if is_correct:
            correct += 1

        std = q.get("standard_code", "")
        if std:
            if std not in standards_mastery:
                standards_mastery[std] = {"total": 0, "correct": 0}
            standards_mastery[std]["total"] += 1
            if is_correct:
                standards_mastery[std]["correct"] += 1

    percentage = round(correct / max(max_score, 1) * 100, 1)

    # Store submission
    submission_id = str(uuid4())
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO interactive_submissions
           (submission_id, activity_id, student_name, responses_json,
            score, max_score, percentage, time_spent_seconds, standards_mastery_json)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (submission_id, activity_id, student_name, Json(responses),
         correct, max_score, percentage, time_spent, Json(standards_mastery)),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        "submission_id": submission_id,
        "score": correct,
        "max_score": max_score,
        "percentage": percentage,
        "time_spent": time_spent,
    }
