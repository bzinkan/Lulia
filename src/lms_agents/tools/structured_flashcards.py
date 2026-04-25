"""
Structured flashcards activity generator.

Gemini emits {title, cards: [{front, back}]}. The HTML template (with a
human-authored React PlayFlashcards component) handles flipping, advance,
and "knew it / didn't" tracking.
"""
import json
import logging

from src.lms_agents.tools.structured_common import (
    call_gemini_json,
    deploy_structured_activity,
)

log = logging.getLogger(__name__)


def _generate_cards(topic: str, grade: str, subject: str,
                    standards: list[str] | None, target_count: int) -> dict:
    standards_line = f"\nAligned standards: {', '.join(standards)}" if standards else ""
    prompt = f"""Create flashcard content for a K-12 study activity.

TOPIC: {topic}
SUBJECT: {subject}
GRADE LEVEL: {grade}{standards_line}

Produce {target_count} flashcards. Each card has a `front` (prompt / term / question) and a `back` (definition / answer / explanation).

RULES:
- `front`: 1-6 words — a term, key vocabulary word, person, date, or short question.
- `back`: a full, age-appropriate definition or answer in 1-2 sentences (under ~200 characters).
- Do NOT repeat the `front` verbatim inside `back`.
- Stay strictly on topic. Use grade-{grade} vocabulary.

Output ONLY JSON, no markdown fences:
{{
  "title": "<short title, max 60 chars>",
  "cards": [
    {{"front": "Photosynthesis", "back": "The process plants use to turn sunlight, water, and carbon dioxide into food."}}
  ]
}}"""
    data = call_gemini_json(prompt)
    cleaned = []
    seen = set()
    for c in data.get("cards", []) or []:
        if not isinstance(c, dict):
            continue
        front = str(c.get("front", "")).strip()
        back = str(c.get("back", "")).strip()
        if not front or not back:
            continue
        if len(front) > 80 or len(back) > 400:
            continue
        if front.lower() in seen:
            continue
        seen.add(front.lower())
        cleaned.append({"front": front, "back": back})
    if len(cleaned) < 3:
        raise ValueError(f"Gemini returned only {len(cleaned)} usable cards")
    title = str(data.get("title", "") or "Flashcards").strip()[:80]
    return {"title": title, "cards": cleaned[:target_count]}


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
.app { max-width: 560px; width: 100%; background: #FEF9F2; border-radius: 20px; padding: 28px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
h1 { font-family: 'DM Serif Display', serif; color: #F97316; font-size: 26px; margin-bottom: 4px; text-align: center; }
.subtitle { color: #78716C; font-size: 13px; margin-bottom: 20px; text-align: center; }
.progress { height: 6px; background: #E7E5E4; border-radius: 3px; margin-bottom: 18px; overflow: hidden; }
.progress-bar { height: 100%; background: #F97316; transition: width 0.3s; }
.flash-stage { perspective: 1400px; margin-bottom: 18px; }
.flash-card { position: relative; width: 100%; height: 320px; transform-style: preserve-3d; transition: transform 0.6s ease; cursor: pointer; }
.flash-card.flipped { transform: rotateY(180deg); }
.flash-face { position: absolute; inset: 0; backface-visibility: hidden; border-radius: 16px; padding: 24px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; box-shadow: 0 4px 14px rgba(0,0,0,0.08); }
.flash-front { background: white; border: 2px solid #F5DEC3; }
.flash-back { background: #FFF7ED; border: 2px solid #FDBA74; transform: rotateY(180deg); }
.flash-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #A8A29E; margin-bottom: 12px; font-weight: 600; }
.flash-term { font-family: 'DM Serif Display', serif; font-size: 30px; color: #1C1917; line-height: 1.2; }
.flash-def { font-size: 17px; color: #1C1917; line-height: 1.5; max-width: 100%; }
.flash-hint { position: absolute; bottom: 12px; left: 0; right: 0; text-align: center; font-size: 11px; color: #A8A29E; }
.flash-controls { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.btn { border: none; border-radius: 10px; padding: 10px 20px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: 'DM Sans'; }
.btn-primary { background: #F97316; color: white; }
.btn-primary:hover { background: #EA580C; }
.btn-secondary { background: white; color: #78350F; border: 1px solid #E7E5E4; }
.btn-secondary:hover { background: #FFF7ED; }
.btn-good { background: #DCFCE7; color: #15803D; }
.btn-good:hover { background: #BBF7D0; }
.btn-hard { background: #FEE2E2; color: #B91C1C; }
.btn-hard:hover { background: #FECACA; }
.results { text-align: center; padding: 20px; }
.results h2 { font-family: 'DM Serif Display', serif; color: #F97316; font-size: 28px; margin-bottom: 8px; }
.results .big { font-size: 48px; font-weight: 700; color: #F97316; margin: 10px 0; }
.results ul { text-align: left; margin-top: 16px; list-style: none; padding: 0; }
.results li { background: white; border-radius: 10px; padding: 10px 14px; margin-bottom: 6px; border-left: 4px solid #EF4444; }
.results li .term { font-weight: 700; color: #1C1917; }
.results li .def { font-size: 13px; color: #57534E; margin-top: 4px; }
.meta { text-align: center; font-size: 12px; color: #78716C; margin-bottom: 12px; }
.logo { text-align: center; font-size: 11px; color: #A8A29E; margin-top: 16px; }
</style></head>
<body>
<div id="root"></div>
<script type="text/babel">
const DATA = __DATA_JSON__;

function PlayFlashcards({ data }) {
  const cards = data.cards || [];
  const total = cards.length;
  const [idx, setIdx] = React.useState(0);
  const [flipped, setFlipped] = React.useState(false);
  const [outcomes, setOutcomes] = React.useState({});
  const [done, setDone] = React.useState(false);

  function rate(knew) {
    setOutcomes(o => ({ ...o, [idx]: knew ? "known" : "review" }));
    if (idx < total - 1) { setIdx(i => i + 1); setFlipped(false); }
    else { setDone(true); }
  }

  if (done) {
    const known = Object.values(outcomes).filter(v => v === "known").length;
    const pct = Math.round((known / Math.max(total, 1)) * 100);
    const toReview = cards.filter((_, i) => outcomes[i] === "review");
    return (
      <div className="app">
        <div className="results">
          <h2>All done!</h2>
          <div className="big">{known} / {total}</div>
          <div style={{ color: "#78716C", fontSize: 14 }}>{pct}% known</div>
          {toReview.length > 0 && (
            <>
              <div className="meta" style={{ marginTop: 18 }}>Review these:</div>
              <ul>
                {toReview.map((c, i) => (
                  <li key={i}><div className="term">{c.front}</div><div className="def">{c.back}</div></li>
                ))}
              </ul>
            </>
          )}
          <button className="btn btn-secondary" onClick={() => { setIdx(0); setFlipped(false); setOutcomes({}); setDone(false); }} style={{ marginTop: 18 }}>Start over</button>
          <div className="logo">Powered by Lulia AI</div>
        </div>
      </div>
    );
  }

  const card = cards[idx];
  const progress = ((idx) / Math.max(total, 1)) * 100;

  return (
    <div className="app">
      <h1>{data.title || "Flashcards"}</h1>
      <div className="subtitle">Tap the card to flip. Rate yourself to move on.</div>
      <div className="progress"><div className="progress-bar" style={{ width: progress + "%" }} /></div>
      <div className="meta">Card {idx + 1} of {total}</div>
      <div className="flash-stage">
        <div className={"flash-card" + (flipped ? " flipped" : "")} onClick={() => setFlipped(f => !f)}>
          <div className="flash-face flash-front">
            <div className="flash-label">Definition</div>
            <div className="flash-def">{card.back}</div>
            <div className="flash-hint">Tap to reveal the term</div>
          </div>
          <div className="flash-face flash-back">
            <div className="flash-label">Term</div>
            <div className="flash-term">{card.front}</div>
            <div className="flash-hint">Tap to flip back</div>
          </div>
        </div>
      </div>
      {flipped ? (
        <div className="flash-controls">
          <button className="btn btn-hard" onClick={() => rate(false)}>Need to review</button>
          <button className="btn btn-good" onClick={() => rate(true)}>I knew this</button>
        </div>
      ) : (
        <div className="flash-controls">
          <button className="btn btn-primary" onClick={() => setFlipped(true)}>Show answer</button>
        </div>
      )}
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<PlayFlashcards data={DATA} />);
</script></body></html>
"""


def _build_html(data: dict) -> str:
    title = (data.get("title") or "Flashcards").replace("<", "").replace(">", "")
    payload = json.dumps(data).replace("</", "<\\/")
    return _HTML.replace("__TITLE__", title).replace("__DATA_JSON__", payload)


def generate_flashcards_activity(
    topic: str, grade: str, subject: str,
    teacher_id: str, class_id: str,
    standards: list | None = None,
    question_count: int = 10,
) -> dict:
    log.info(f"[Flashcards] topic='{topic[:60]}' grade={grade} subject={subject} count={question_count}")
    data = _generate_cards(topic, grade, subject, standards, question_count)
    html = _build_html(data)
    return deploy_structured_activity(
        html=html,
        template_id="flash_cards_interactive",
        title=data.get("title", "Flashcards"),
        teacher_id=teacher_id, class_id=class_id,
        standards=standards,
        content_summary={"topic": topic, "subject": subject, "grade": grade,
                         "card_count": len(data["cards"])},
        full_data=data,
        questions_for_assignment=[{"term": c["front"], "definition": c["back"]} for c in data["cards"]],
    )
