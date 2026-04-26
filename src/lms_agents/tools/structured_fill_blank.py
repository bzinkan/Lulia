"""
Structured fill-in-the-blank activity.

Gemini emits {title, word_bank, items: [{sentence, answer, hint?}]}.
Sentences contain exactly one "___" (three underscores) marking the blank.
The engine renders the sentence with an inline <input>, compares student's
typed answer to the expected answer (case-insensitive, stripped), and
optionally shows a shuffled word-bank row for scaffolded practice.
"""
import json
import logging
import re

from src.lms_agents.tools.structured_common import (
    call_gemini_json,
    deploy_structured_activity,
    fetch_grounding_context,
)

log = logging.getLogger(__name__)


def _generate_items(topic: str, grade: str, subject: str,
                    standards: list[str] | None, target_count: int,
                    teacher_id: str | None = None) -> dict:
    standards_line = f"\nAligned standards: {', '.join(standards)}" if standards else ""
    grounding = fetch_grounding_context(
        topic=topic, grade=grade, subject=subject,
        standards=standards, teacher_id=teacher_id,
    )
    prompt = f"""Create fill-in-the-blank questions for a K-12 activity.

TOPIC: {topic}
SUBJECT: {subject}
GRADE LEVEL: {grade}{standards_line}

{grounding}
Prefer sentences and vocabulary from the textbook material above when relevant — students should recognize the language.

Produce {target_count} items. Each item is ONE sentence with EXACTLY ONE blank marked by three underscores (___). The answer is the word or short phrase that fills the blank.

RULES:
- sentence: one complete sentence with "___" where the missing word goes. Nowhere else in the sentence should the answer appear.
- answer: 1-3 words, no punctuation, lowercase preferred. Must be a short distinctive term.
- hint: OPTIONAL short clue (under 50 chars). Omit if the sentence itself is clear enough.
- Answers should be distinct across items — no duplicate answers in the same activity.
- Stay tightly on topic. Grade-{grade} vocabulary.
- Do NOT use the answer word elsewhere in the sentence.

Output ONLY JSON, no markdown:
{{
  "title": "<short title, max 60 chars>",
  "items": [
    {{"sentence": "The ___ is the powerhouse of the cell.", "answer": "mitochondria"}},
    {{"sentence": "Green plants use ___ to make their own food.", "answer": "photosynthesis"}}
  ]
}}"""
    data = call_gemini_json(prompt)
    title = str(data.get("title", "") or "Fill in the Blank").strip()[:80]
    cleaned = []
    seen = set()
    for it in data.get("items", []) or []:
        if not isinstance(it, dict):
            continue
        sentence = str(it.get("sentence", "")).strip()
        answer = str(it.get("answer", "")).strip()
        hint = str(it.get("hint", "") or "").strip() or None
        if not sentence or not answer:
            continue
        # Normalize: ensure sentence has "___"; if not, try to inject it
        if "___" not in sentence:
            # If the answer appears in the sentence, blank it out; otherwise skip
            pattern = re.compile(re.escape(answer), re.IGNORECASE)
            if pattern.search(sentence):
                sentence = pattern.sub("___", sentence, count=1)
            else:
                continue
        # Reject sentences that still contain the answer verbatim (data leak)
        if re.search(rf"\b{re.escape(answer)}\b", sentence, re.IGNORECASE):
            continue
        key = answer.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"sentence": sentence, "answer": answer, "hint": hint})
    if len(cleaned) < 3:
        raise ValueError(f"Gemini returned only {len(cleaned)} usable fill-in items")
    return {
        "title": title,
        "word_bank": True,
        "items": cleaned[:target_count],
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
body { font-family: 'DM Sans', sans-serif; background: #F5DEC3; min-height: 100vh; padding: 24px; display: flex; align-items: flex-start; justify-content: center; }
.app { max-width: 680px; width: 100%; background: #FEF9F2; border-radius: 20px; padding: 26px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
h1 { font-family: 'DM Serif Display', serif; color: #F97316; font-size: 26px; margin-bottom: 4px; }
.subtitle { color: #78716C; font-size: 13px; margin-bottom: 18px; }
.bank { background: white; border: 1px solid #E7E5E4; border-radius: 10px; padding: 10px 14px; margin-bottom: 16px; }
.bank-title { font-family: 'DM Serif Display', serif; color: #78350F; font-size: 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
.bank-title .count { font-family: 'DM Sans'; font-size: 11px; color: #A8A29E; font-weight: 500; }
.bank-words { display: flex; flex-wrap: wrap; gap: 6px; }
.bank-word { font-size: 13px; font-weight: 600; padding: 5px 12px; border-radius: 999px; background: #FFEDD5; color: #7C2D12; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; }
.bank-word:hover { border-color: #FDBA74; }
.bank-word.used { background: #F5F5F4; color: #A8A29E; text-decoration: line-through; cursor: default; }
.items { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.item { background: white; border-radius: 12px; padding: 14px 16px; border: 1px solid #E7E5E4; }
.item-text { font-size: 15px; color: #1C1917; line-height: 1.6; }
.item-hint { font-size: 11px; color: #A8A29E; margin-top: 6px; font-style: italic; }
.blank-input { display: inline-block; min-width: 120px; border: none; border-bottom: 2px solid #F97316; background: transparent; padding: 2px 6px; font-size: 15px; font-family: inherit; color: #1C1917; outline: none; font-weight: 600; text-align: center; }
.blank-input:focus { border-bottom-color: #EA580C; background: #FFF7ED; }
.blank-input.correct { border-bottom-color: #22C55E; color: #15803D; background: #DCFCE7; }
.blank-input.wrong { border-bottom-color: #EF4444; color: #B91C1C; background: #FEE2E2; }
.reveal { font-size: 12px; color: #DC2626; font-weight: 600; margin-top: 6px; }
.controls { display: flex; gap: 10px; flex-wrap: wrap; }
.btn { border: none; border-radius: 10px; padding: 10px 22px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: 'DM Sans'; }
.btn-primary { background: #F97316; color: white; }
.btn-primary:hover { background: #EA580C; }
.btn-secondary { background: white; color: #78350F; border: 1px solid #E7E5E4; }
.btn-secondary:hover { background: #FFF7ED; }
.status { margin-top: 14px; padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600; }
.status.good { background: #DCFCE7; color: #15803D; }
.status.partial { background: #FEF3C7; color: #A16207; }
.logo { text-align: center; font-size: 11px; color: #A8A29E; margin-top: 16px; }
</style></head>
<body>
<div id="root"></div>
<script type="text/babel">
const DATA = __DATA_JSON__;

function shuffled(arr) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }

function PlayFillBlank({ data }) {
  const items = data.items || [];
  const useBank = !!data.word_bank;
  const [bankOrder] = React.useState(() => shuffled(items.map(it => it.answer)));
  const [typed, setTyped] = React.useState({});
  const [checked, setChecked] = React.useState(false);
  const [focused, setFocused] = React.useState(null);
  const inputRefs = React.useRef({});

  function normalize(s) { return String(s || "").trim().toLowerCase(); }
  function isCorrect(i) { return normalize(typed[i]) === normalize(items[i].answer); }

  function onChange(i, v) { setTyped(t => ({ ...t, [i]: v })); }
  function onPick(word) {
    if (checked) return;
    let target = focused;
    if (target == null || isCorrect(target)) {
      // Find first blank that isn't already correct
      for (let i = 0; i < items.length; i++) {
        if (!isCorrect(i)) { target = i; break; }
      }
    }
    if (target == null) return;
    setTyped(t => ({ ...t, [target]: word }));
    // Auto-focus next empty
    const next = items.findIndex((_, j) => j > target && !typed[j]);
    if (next >= 0) {
      setFocused(next);
      setTimeout(() => inputRefs.current[next]?.focus(), 0);
    }
  }
  function check() { setChecked(true); }
  function reset() { setTyped({}); setChecked(false); }

  // Track which bank words have been placed correctly (case-insensitive)
  const usedAnswers = new Set(
    items
      .map((it, i) => (normalize(typed[i]) === normalize(it.answer) ? normalize(it.answer) : null))
      .filter(Boolean)
  );

  const correctCount = items.filter((_, i) => isCorrect(i)).length;
  const allCorrect = checked && correctCount === items.length;

  return (
    <div className="app">
      <h1>{data.title || "Fill in the Blank"}</h1>
      <div className="subtitle">{useBank ? "Click a word in the bank or type directly." : "Type the missing word in each blank."}</div>

      {useBank && (
        <div className="bank">
          <div className="bank-title">
            <span>Word bank</span>
            <span className="count">{usedAnswers.size} / {bankOrder.length} placed</span>
          </div>
          <div className="bank-words">
            {bankOrder.map(w => {
              const used = usedAnswers.has(normalize(w));
              return (
                <span key={w} className={"bank-word" + (used ? " used" : "")}
                      onClick={() => !used && onPick(w)}>
                  {w}
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div className="items">
        {items.map((it, i) => {
          const parts = it.sentence.split(/___+/);
          const before = parts[0] || "";
          const after = parts.slice(1).join("___");
          const val = typed[i] || "";
          const correct = checked && isCorrect(i);
          const wrong = checked && val && !correct;
          const empty = checked && !val;
          const cls = "blank-input" + (correct ? " correct" : "") + ((wrong || empty) ? " wrong" : "");
          return (
            <div key={i} className="item">
              <div className="item-text">
                {before}
                <input ref={el => { inputRefs.current[i] = el; }}
                  className={cls}
                  value={val}
                  readOnly={checked && correct}
                  onChange={e => !checked || !isCorrect(i) ? onChange(i, e.target.value) : null}
                  onFocus={() => setFocused(i)}
                  placeholder="_____" />
                {after}
              </div>
              {it.hint && !checked && <div className="item-hint">Hint: {it.hint}</div>}
              {checked && !isCorrect(i) && (
                <div className="reveal">Answer: {it.answer}</div>
              )}
            </div>
          );
        })}
      </div>

      {checked && (
        <div className={"status " + (allCorrect ? "good" : "partial")}>
          {allCorrect
            ? `✓ Perfect — all ${items.length} blanks filled correctly!`
            : `${correctCount} of ${items.length} correct.`}
        </div>
      )}

      <div className="controls" style={{ marginTop: 14 }}>
        {!checked
          ? <button className="btn btn-primary" onClick={check}>Check answers</button>
          : <button className="btn btn-secondary" onClick={reset}>Try again</button>}
      </div>
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<PlayFillBlank data={DATA} />);
</script></body></html>
"""


def _build_html(data: dict) -> str:
    title = (data.get("title") or "Fill in the Blank").replace("<", "").replace(">", "")
    payload = json.dumps(data).replace("</", "<\\/")
    return _HTML.replace("__TITLE__", title).replace("__DATA_JSON__", payload)


def generate_fill_blank_activity(
    topic: str, grade: str, subject: str,
    teacher_id: str, class_id: str,
    standards: list | None = None,
    question_count: int = 10,
) -> dict:
    log.info(f"[FillBlank] topic='{topic[:60]}' grade={grade} subject={subject} count={question_count}")
    data = _generate_items(topic, grade, subject, standards, question_count, teacher_id=teacher_id)
    html = _build_html(data)
    return deploy_structured_activity(
        html=html,
        template_id="fill_in_blank",
        title=data.get("title", "Fill in the Blank"),
        teacher_id=teacher_id, class_id=class_id,
        standards=standards,
        content_summary={"topic": topic, "subject": subject, "grade": grade,
                         "item_count": len(data["items"])},
        full_data=data,
        questions_for_assignment=[{"sentence": it["sentence"], "answer": it["answer"]} for it in data["items"]],
    )
