"""
Structured number-line activity.

Gemini returns {title, min, max, interval, questions: [{text, answer}]}.
Students tap on the line to place a value; a tolerance of half the interval
counts as correct.
"""
import json
import logging

from src.lms_agents.tools.structured_common import (
    call_gemini_json,
    deploy_structured_activity,
    fetch_grounding_context,
)

log = logging.getLogger(__name__)


def _generate_questions(topic: str, grade: str, subject: str,
                        standards: list[str] | None, target_count: int,
                        teacher_id: str | None = None) -> dict:
    standards_line = f"\nAligned standards: {', '.join(standards)}" if standards else ""
    grounding = fetch_grounding_context(
        topic=topic, grade=grade, subject=subject,
        standards=standards, teacher_id=teacher_id,
    )
    prompt = f"""You are designing a K-12 number-line placement activity.

TOPIC: {topic}
SUBJECT: {subject}
GRADE LEVEL: {grade}{standards_line}

{grounding}
Choose a suitable numeric range (`min`, `max`) and tick interval for the line based on the topic and grade. Then produce {target_count} short questions. For each question, the student will tap a location on the line to answer.

RULES:
- `min` < `max`; both integers or simple decimals.
- `interval` is the tick spacing (e.g. 1, 2, 5, 10, 0.5).
- The line should span all answer values with a little padding on each side.
- Every `answer` must be a single number between `min` and `max` inclusive.
- `text` is a short grade-{grade} question (under 100 chars) — e.g. "Where is 6 on the line?", "Place 3/4 on the line.", "Find the temperature where water freezes in Celsius.".
- Mix difficulty: some direct values, some small word problems.

Output ONLY JSON:
{{
  "title": "<short title, max 60 chars>",
  "min": 0,
  "max": 20,
  "interval": 1,
  "questions": [
    {{"text": "Where is 7 on the line?", "answer": 7}},
    {{"text": "Mark the number that is 3 more than 5.", "answer": 8}}
  ]
}}"""
    data = call_gemini_json(prompt)
    title = str(data.get("title", "") or "Number Line").strip()[:80]
    try:
        nmin = float(data.get("min"))
        nmax = float(data.get("max"))
        interval = float(data.get("interval", 1))
    except Exception as e:
        raise ValueError(f"Invalid numeric range: {e}")
    if not (nmin < nmax) or interval <= 0:
        raise ValueError(f"Bad min/max/interval: {nmin}/{nmax}/{interval}")

    cleaned = []
    for q in data.get("questions", []) or []:
        if not isinstance(q, dict):
            continue
        text = str(q.get("text", "")).strip()
        try:
            ans = float(q.get("answer"))
        except Exception:
            continue
        if not text or ans < nmin or ans > nmax:
            continue
        cleaned.append({"text": text, "answer": ans})
    if len(cleaned) < 3:
        raise ValueError(f"Gemini returned only {len(cleaned)} usable questions")
    return {
        "title": title, "min": nmin, "max": nmax, "interval": interval,
        "questions": cleaned[:target_count],
    }


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__ — Lulia</title>
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'DM Sans', sans-serif; background: #F5DEC3; min-height: 100vh; padding: 24px; display: flex; align-items: center; justify-content: center; }
.app { max-width: 640px; width: 100%; background: #FEF9F2; border-radius: 20px; padding: 28px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
h1 { font-family: 'DM Serif Display', serif; color: #F97316; font-size: 26px; margin-bottom: 4px; }
.subtitle { color: #78716C; font-size: 13px; margin-bottom: 18px; }
.progress { height: 6px; background: #E7E5E4; border-radius: 3px; margin-bottom: 18px; overflow: hidden; }
.progress-bar { height: 100%; background: #F97316; transition: width 0.3s; }
.meta { font-size: 12px; color: #78716C; margin-bottom: 10px; display: flex; justify-content: space-between; }
.card { background: white; border-radius: 14px; padding: 18px; margin-bottom: 14px; }
.card h2 { font-family: 'DM Serif Display', serif; color: #78350F; font-size: 18px; margin-bottom: 10px; }
.nl-wrap { padding: 14px 6px; background: #FFF7ED; border-radius: 10px; margin-top: 8px; user-select: none; -webkit-user-select: none; touch-action: manipulation; }
.btn { border: none; border-radius: 10px; padding: 10px 22px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: 'DM Sans'; }
.btn-primary { background: #F97316; color: white; width: 100%; }
.btn-primary:hover { background: #EA580C; }
.btn-primary:disabled { background: #FDBA74; cursor: not-allowed; }
.status { padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600; margin-top: 12px; }
.status.correct { background: #DCFCE7; color: #15803D; }
.status.wrong { background: #FEE2E2; color: #B91C1C; }
.results { text-align: center; padding: 10px; }
.results .big { font-size: 48px; font-weight: 700; color: #F97316; }
.results .sub { font-size: 14px; color: #78716C; margin-bottom: 16px; }
.logo { text-align: center; font-size: 11px; color: #A8A29E; margin-top: 16px; }
</style></head>
<body>
<div id="root"></div>
<script type="text/babel">
const DATA = __DATA_JSON__;

const SVG_W = 560, SVG_H = 100, MARGIN_X = 30, LINE_Y = 55;

function PlayNumberLine({ data }) {
  const qs = data.questions || [];
  const nmin = Number(data.min), nmax = Number(data.max), interval = Number(data.interval) || 1;
  const [idx, setIdx] = React.useState(0);
  const [placed, setPlaced] = React.useState({});
  const [feedback, setFeedback] = React.useState({});
  const [done, setDone] = React.useState(false);
  const svgRef = React.useRef(null);

  function xForValue(v) {
    const frac = (v - nmin) / (nmax - nmin);
    return MARGIN_X + frac * (SVG_W - 2 * MARGIN_X);
  }
  function valueForX(x) {
    const frac = (x - MARGIN_X) / (SVG_W - 2 * MARGIN_X);
    return nmin + frac * (nmax - nmin);
  }

  function handleClick(e) {
    if (!svgRef.current) return;
    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const clientX = e.clientX ?? (e.touches && e.touches[0] && e.touches[0].clientX);
    if (clientX == null) return;
    const xSvg = ((clientX - rect.left) / rect.width) * SVG_W;
    let v = valueForX(xSvg);
    // Snap to nearest interval
    v = Math.round(v / interval) * interval;
    if (v < nmin) v = nmin;
    if (v > nmax) v = nmax;
    setPlaced(p => ({ ...p, [idx]: v }));
    setFeedback({}); // clear prior feedback when they reposition
  }

  function submit() {
    const q = qs[idx];
    const placement = placed[idx];
    if (placement === undefined) return;
    const tol = interval / 2 + 1e-9;
    const correct = Math.abs(placement - q.answer) <= tol;
    setFeedback({ [idx]: { correct, placement, answer: q.answer } });
    setTimeout(() => {
      if (idx < qs.length - 1) { setIdx(i => i + 1); setFeedback({}); }
      else { setDone(true); }
    }, correct ? 800 : 1500);
  }

  if (done) {
    const correctCount = qs.filter((q, i) => {
      const p = placed[i];
      if (p === undefined) return false;
      return Math.abs(p - q.answer) <= interval / 2 + 1e-9;
    }).length;
    return (
      <div className="app">
        <div className="results">
          <div className="big">{correctCount} / {qs.length}</div>
          <div className="sub">{Math.round((correctCount / Math.max(qs.length, 1)) * 100)}% correct</div>
          <button className="btn btn-primary" onClick={() => { setIdx(0); setPlaced({}); setFeedback({}); setDone(false); }}>Try again</button>
          <div className="logo">Powered by Lulia AI</div>
        </div>
      </div>
    );
  }

  const q = qs[idx];
  const placement = placed[idx];
  const fb = feedback[idx];
  const progress = ((idx) / qs.length) * 100;

  // Tick marks
  const ticks = [];
  for (let v = nmin; v <= nmax + 1e-9; v += interval) {
    ticks.push(Math.round(v * 1000) / 1000);
  }

  return (
    <div className="app">
      <h1>{data.title || "Number Line"}</h1>
      <div className="subtitle">Tap the line to place your answer. Values snap to the nearest tick.</div>
      <div className="progress"><div className="progress-bar" style={{ width: progress + "%" }} /></div>
      <div className="meta"><span>Question {idx + 1} of {qs.length}</span><span>Range: {nmin} to {nmax}</span></div>
      <div className="card">
        <h2>{q.text}</h2>
        <div className="nl-wrap">
          <svg ref={svgRef} viewBox={`0 0 ${SVG_W} ${SVG_H}`} width="100%" style={{ display: "block", cursor: "crosshair" }}
               onClick={handleClick}>
            <line x1={MARGIN_X} y1={LINE_Y} x2={SVG_W - MARGIN_X} y2={LINE_Y} stroke="#78716C" strokeWidth="2" />
            <polygon points={`${MARGIN_X - 8},${LINE_Y} ${MARGIN_X},${LINE_Y - 6} ${MARGIN_X},${LINE_Y + 6}`} fill="#78716C" />
            <polygon points={`${SVG_W - MARGIN_X + 8},${LINE_Y} ${SVG_W - MARGIN_X},${LINE_Y - 6} ${SVG_W - MARGIN_X},${LINE_Y + 6}`} fill="#78716C" />
            {ticks.map((v, i) => (
              <g key={i}>
                <line x1={xForValue(v)} y1={LINE_Y - 5} x2={xForValue(v)} y2={LINE_Y + 5} stroke="#78716C" strokeWidth="1.5" />
                <text x={xForValue(v)} y={LINE_Y + 20} fontSize="11" textAnchor="middle" fill="#78716C">{v}</text>
              </g>
            ))}
            {placement !== undefined && (
              <g>
                <circle cx={xForValue(placement)} cy={LINE_Y} r="9"
                        fill={fb ? (fb.correct ? "#22C55E" : "#EF4444") : "#F97316"}
                        stroke="white" strokeWidth="2" />
                <text x={xForValue(placement)} y={LINE_Y - 14} fontSize="12" textAnchor="middle"
                      fill={fb ? (fb.correct ? "#15803D" : "#B91C1C") : "#F97316"} fontWeight="bold">
                  {Math.round(placement * 1000) / 1000}
                </text>
              </g>
            )}
            {fb && !fb.correct && (
              <g>
                <circle cx={xForValue(q.answer)} cy={LINE_Y} r="7" fill="#22C55E" stroke="white" strokeWidth="2" opacity="0.85" />
                <text x={xForValue(q.answer)} y={LINE_Y + 40} fontSize="11" textAnchor="middle" fill="#15803D" fontWeight="bold">
                  ✓ {q.answer}
                </text>
              </g>
            )}
          </svg>
        </div>
        {fb && (
          <div className={"status " + (fb.correct ? "correct" : "wrong")}>
            {fb.correct ? "✓ Correct!" : `Close! The answer was ${q.answer}.`}
          </div>
        )}
      </div>
      <button className="btn btn-primary" disabled={placement === undefined || !!fb} onClick={submit}>
        {idx < qs.length - 1 ? "Submit" : "Submit & finish"}
      </button>
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<PlayNumberLine data={DATA} />);
</script></body></html>
"""


def _build_html(data: dict) -> str:
    title = (data.get("title") or "Number Line").replace("<", "").replace(">", "")
    payload = json.dumps(data).replace("</", "<\\/")
    return _HTML.replace("__TITLE__", title).replace("__DATA_JSON__", payload)


def generate_number_line_activity(
    topic: str, grade: str, subject: str,
    teacher_id: str, class_id: str,
    standards: list | None = None,
    question_count: int = 8,
) -> dict:
    log.info(f"[NumberLine] topic='{topic[:60]}' grade={grade} subject={subject} count={question_count}")
    data = _generate_questions(topic, grade, subject, standards, question_count, teacher_id=teacher_id)
    html = _build_html(data)
    return deploy_structured_activity(
        html=html,
        template_id="number_line",
        title=data.get("title", "Number Line"),
        teacher_id=teacher_id, class_id=class_id,
        standards=standards,
        content_summary={"topic": topic, "subject": subject, "grade": grade,
                         "range": [data["min"], data["max"]], "interval": data["interval"],
                         "question_count": len(data["questions"])},
        full_data=data,
        questions_for_assignment=data["questions"],
    )
