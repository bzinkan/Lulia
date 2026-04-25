"""
Structured timeline activity.

Gemini returns {title, events: [{label, date, description?}]}. The student
sees shuffled events and clicks them in the order they believe is correct
chronologically. On Check, the student's ordering is compared to the true
chronological order.
"""
import json
import logging
import re

from src.lms_agents.tools.structured_common import (
    call_gemini_json,
    deploy_structured_activity,
)

log = logging.getLogger(__name__)


def _parse_year(date: str) -> float | None:
    """Return a sortable year-ish number from a string.
    Supports 'YYYY', 'YYYY-MM-DD', 'Month YYYY', '450 BC', 'c. 1500'."""
    s = str(date).strip()
    if not s:
        return None
    # Negative-year detection first (BC / BCE)
    mbc = re.search(r"(-?\d{1,5})\s*(bc|bce)\b", s, re.IGNORECASE)
    if mbc:
        try:
            return -abs(int(mbc.group(1)))
        except Exception:
            return None
    # ISO-ish date
    miso = re.match(r"^(-?\d{1,5})(?:-\d{1,2})?(?:-\d{1,2})?$", s)
    if miso:
        try:
            return float(miso.group(1))
        except Exception:
            return None
    # Four-digit year anywhere
    m4 = re.search(r"(-?\d{3,5})", s)
    if m4:
        try:
            return float(m4.group(1))
        except Exception:
            return None
    return None


def _generate_events(topic: str, grade: str, subject: str,
                     standards: list[str] | None, target_count: int) -> dict:
    standards_line = f"\nAligned standards: {', '.join(standards)}" if standards else ""
    prompt = f"""You are designing a K-12 chronological-order activity.

TOPIC: {topic}
SUBJECT: {subject}
GRADE LEVEL: {grade}{standards_line}

Produce {target_count} events the student will arrange in chronological order.

RULES:
- `label`: short name of the event (under 70 chars).
- `date`: a string the reader can quickly understand — e.g. "1776", "1969-07-20", "March 1865", "450 BC". Prefer simple years.
- `description`: one sentence of grade-{grade} context (under 160 chars). Optional but encouraged.
- Events should span enough time that ordering matters — don't cluster them all in one year.
- Stay strictly on the topic.
- Do NOT put the date inside `label` or `description` — the student should rely on domain knowledge, not text hints.

Output ONLY JSON:
{{
  "title": "<short title, max 60 chars>",
  "events": [
    {{"label": "Declaration of Independence signed", "date": "1776",
      "description": "Colonies formally declare independence from Britain."}},
    {{"label": "Civil War ends at Appomattox", "date": "1865",
      "description": "General Lee surrenders to General Grant."}}
  ]
}}"""
    data = call_gemini_json(prompt)
    title = str(data.get("title", "") or "Timeline").strip()[:80]
    cleaned = []
    for e in data.get("events", []) or []:
        if not isinstance(e, dict):
            continue
        label = str(e.get("label", "")).strip()
        date = str(e.get("date", "")).strip()
        desc = str(e.get("description", "") or "").strip()
        year = _parse_year(date)
        if not label or year is None:
            continue
        cleaned.append({"label": label[:120], "date": date, "description": desc[:200], "year": year})
    # Dedupe by label
    seen = set()
    uniq = []
    for e in cleaned:
        key = e["label"].lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    if len(uniq) < 3:
        raise ValueError(f"Gemini returned only {len(uniq)} usable events")
    uniq.sort(key=lambda e: e["year"])
    return {"title": title, "events": uniq[:target_count]}


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
.app { max-width: 720px; width: 100%; background: #FEF9F2; border-radius: 20px; padding: 26px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
h1 { font-family: 'DM Serif Display', serif; color: #F97316; font-size: 26px; margin-bottom: 4px; }
.subtitle { color: #78716C; font-size: 13px; margin-bottom: 18px; }
.tl-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.tl-item { background: white; border: 2px solid #E7E5E4; border-radius: 12px; padding: 12px 16px; cursor: pointer; display: flex; gap: 12px; align-items: flex-start; transition: all 0.15s; }
.tl-item:hover { border-color: #FDBA74; background: #FFF7ED; }
.tl-item.picked { border-color: #F97316; background: #FFF7ED; }
.tl-item.correct { border-color: #22C55E; background: #DCFCE7; }
.tl-item.wrong { border-color: #EF4444; background: #FEE2E2; }
.tl-badge { flex: 0 0 auto; width: 34px; height: 34px; border-radius: 999px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 15px; background: #F5DEC3; color: #78350F; }
.tl-item.picked .tl-badge { background: #F97316; color: white; }
.tl-item.correct .tl-badge { background: #22C55E; color: white; }
.tl-item.wrong .tl-badge { background: #EF4444; color: white; }
.tl-body { flex: 1 1 auto; min-width: 0; }
.tl-label { font-weight: 600; color: #1C1917; font-size: 15px; line-height: 1.3; }
.tl-desc { font-size: 12px; color: #78716C; margin-top: 3px; }
.tl-reveal { font-size: 12px; color: #15803D; font-weight: 600; margin-top: 4px; }
.tl-reveal.err { color: #B91C1C; }
.tl-controls { display: flex; gap: 10px; flex-wrap: wrap; }
.btn { border: none; border-radius: 10px; padding: 10px 22px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: 'DM Sans'; }
.btn-primary { background: #F97316; color: white; }
.btn-primary:hover { background: #EA580C; }
.btn-primary:disabled { background: #FDBA74; cursor: not-allowed; }
.btn-secondary { background: white; color: #78350F; border: 1px solid #E7E5E4; }
.btn-secondary:hover { background: #FFF7ED; }
.status { padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600; margin-top: 12px; }
.status.good { background: #DCFCE7; color: #15803D; }
.status.partial { background: #FEF3C7; color: #A16207; }
.logo { text-align: center; font-size: 11px; color: #A8A29E; margin-top: 16px; }
</style></head>
<body>
<div id="root"></div>
<script type="text/babel">
const DATA = __DATA_JSON__;

function PlayTimeline({ data }) {
  const correctOrder = data.events || [];  // Pre-sorted chronologically by server
  // Shuffle once for display
  const [shuffled] = React.useState(() => {
    const arr = correctOrder.map((e, i) => ({ ...e, _origIdx: i }));
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  });
  const [picks, setPicks] = React.useState([]); // list of _origIdx in chosen order
  const [checked, setChecked] = React.useState(false);

  function togglePick(origIdx) {
    if (checked) return;
    if (picks.includes(origIdx)) {
      setPicks(p => p.filter(x => x !== origIdx));
    } else {
      setPicks(p => [...p, origIdx]);
    }
  }
  function doCheck() { setChecked(true); }
  function doReset() { setPicks([]); setChecked(false); }

  // Each pick position == index in picks. Correct if the picked item's origIdx matches that position in chronological order.
  // i.e. picks[0] should have _origIdx === 0, picks[1] === 1, etc.
  const results = checked ? picks.map((origIdx, pos) => ({
    origIdx, pos, correct: origIdx === pos,
  })) : [];
  const score = results.filter(r => r.correct).length;

  return (
    <div className="app">
      <h1>{data.title || "Put it in order"}</h1>
      <div className="subtitle">Tap events in the order you think they happened, earliest first. Tap again to un-pick.</div>
      <div className="tl-list">
        {shuffled.map(ev => {
          const pickPos = picks.indexOf(ev._origIdx);
          const picked = pickPos >= 0;
          const result = results.find(r => r.origIdx === ev._origIdx);
          const cls = "tl-item"
            + (picked && !checked ? " picked" : "")
            + (checked && result && result.correct ? " correct" : "")
            + (checked && result && !result.correct ? " wrong" : "");
          return (
            <div key={ev._origIdx} className={cls} onClick={() => togglePick(ev._origIdx)}>
              <div className="tl-badge">{picked ? pickPos + 1 : "?"}</div>
              <div className="tl-body">
                <div className="tl-label">{ev.label}</div>
                {ev.description && <div className="tl-desc">{ev.description}</div>}
                {checked && result && !result.correct && (
                  <div className="tl-reveal err">Correct position: {ev._origIdx + 1} &nbsp;•&nbsp; Date: {ev.date}</div>
                )}
                {checked && result && result.correct && (
                  <div className="tl-reveal">✓ {ev.date}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {checked ? (
        <>
          <div className={"status " + (score === correctOrder.length ? "good" : "partial")}>
            {score === correctOrder.length
              ? `✓ Perfect — all ${correctOrder.length} events in order!`
              : `${score} of ${picks.length} in the right position.`}
          </div>
          <div className="tl-controls" style={{ marginTop: 12 }}>
            <button className="btn btn-secondary" onClick={doReset}>Try again</button>
          </div>
        </>
      ) : (
        <div className="tl-controls">
          <button className="btn btn-primary" disabled={picks.length < correctOrder.length} onClick={doCheck}>
            Check order ({picks.length} / {correctOrder.length})
          </button>
          <button className="btn btn-secondary" onClick={() => setPicks([])}>Clear</button>
        </div>
      )}
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<PlayTimeline data={DATA} />);
</script></body></html>
"""


def _build_html(data: dict) -> str:
    title = (data.get("title") or "Timeline").replace("<", "").replace(">", "")
    payload = json.dumps(data).replace("</", "<\\/")
    return _HTML.replace("__TITLE__", title).replace("__DATA_JSON__", payload)


def generate_timeline_activity(
    topic: str, grade: str, subject: str,
    teacher_id: str, class_id: str,
    standards: list | None = None,
    question_count: int = 8,
) -> dict:
    log.info(f"[Timeline] topic='{topic[:60]}' grade={grade} subject={subject} count={question_count}")
    data = _generate_events(topic, grade, subject, standards, question_count)
    html = _build_html(data)
    return deploy_structured_activity(
        html=html,
        template_id="timeline",
        title=data.get("title", "Timeline"),
        teacher_id=teacher_id, class_id=class_id,
        standards=standards,
        content_summary={"topic": topic, "subject": subject, "grade": grade,
                         "event_count": len(data["events"])},
        full_data=data,
        questions_for_assignment=data["events"],
    )
