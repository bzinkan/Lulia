"""
Structured word-search activity.

Gemini returns {title, words: ["WORD1", "WORD2", ...]}. The HTML template
places the words into a grid (8 directions, with conflict resolution) and
fills the remaining cells with random letters. Students click-drag across
cells to select a run; if it spells a listed word, that word is marked
found.
"""
import json
import logging
import re

from src.lms_agents.tools.structured_common import (
    call_gemini_json,
    deploy_structured_activity,
)

log = logging.getLogger(__name__)


def _generate_words(topic: str, grade: str, subject: str,
                    standards: list[str] | None, target_count: int) -> dict:
    standards_line = f"\nAligned standards: {', '.join(standards)}" if standards else ""
    prompt = f"""You are designing a K-12 word-search puzzle.

TOPIC: {topic}
SUBJECT: {subject}
GRADE LEVEL: {grade}{standards_line}

Produce between 8 and {target_count} words. Each word must be a single UPPERCASE word, A-Z only, 3-10 letters, directly related to the topic, grade-{grade} appropriate.

Output ONLY JSON, no markdown fences:
{{
  "title": "<short title, max 60 chars>",
  "words": ["NUCLEUS", "ORBIT", ...]
}}"""
    data = call_gemini_json(prompt)
    title = str(data.get("title", "") or "Word Search").strip()[:80]
    cleaned = []
    seen = set()
    for w in data.get("words", []) or []:
        s = re.sub(r"[^A-Z]", "", str(w).upper())
        if not (3 <= len(s) <= 10):
            continue
        if s in seen:
            continue
        seen.add(s)
        cleaned.append(s)
    if len(cleaned) < 4:
        raise ValueError(f"Gemini returned only {len(cleaned)} usable words")
    return {"title": title, "words": cleaned[:target_count]}


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
body { font-family: 'DM Sans', sans-serif; background: #F5DEC3; min-height: 100vh; padding: 24px; }
.app { max-width: 980px; margin: 0 auto; background: #FEF9F2; border-radius: 20px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
h1 { font-family: 'DM Serif Display', serif; color: #F97316; font-size: 26px; margin-bottom: 4px; }
.subtitle { color: #78716C; font-size: 13px; margin-bottom: 18px; }
.ws-layout { display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-start; }
.ws-grid-wrap { flex: 0 0 auto; background: white; padding: 10px; border-radius: 12px; touch-action: none; user-select: none; -webkit-user-select: none; }
.ws-grid { display: grid; gap: 2px; }
.ws-cell { width: 34px; height: 34px; background: #FFF7ED; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: 600; color: #1C1917; font-size: 15px; cursor: pointer; user-select: none; }
.ws-cell.sel { background: #FDBA74; color: #7C2D12; }
.ws-cell.found { background: #DCFCE7; color: #14532D; }
.ws-words { flex: 1 1 220px; min-width: 200px; background: white; border-radius: 12px; padding: 14px 16px; border: 1px solid #E7E5E4; }
.ws-words h3 { font-family: 'DM Serif Display', serif; color: #78350F; font-size: 16px; margin-bottom: 10px; }
.ws-word { padding: 4px 8px; font-size: 13px; color: #1C1917; }
.ws-word.found { color: #16A34A; text-decoration: line-through; }
.controls { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 18px; }
.btn { border: none; border-radius: 10px; padding: 10px 22px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: 'DM Sans'; }
.btn-primary { background: #F97316; color: white; }
.btn-secondary { background: white; color: #78350F; border: 1px solid #E7E5E4; }
.status { margin-top: 14px; padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600; }
.status.good { background: #DCFCE7; color: #15803D; }
.status.partial { background: #FEF3C7; color: #A16207; }
.logo { text-align: center; font-size: 11px; color: #A8A29E; margin-top: 18px; }
@media (max-width: 640px) {
  .ws-cell { width: 28px; height: 28px; font-size: 13px; }
}
</style></head>
<body>
<div id="root"></div>
<script type="text/babel">
const DATA = __DATA_JSON__;

const DIRECTIONS = [
  [1, 0], [0, 1], [1, 1], [1, -1],    // forward
  [-1, 0], [0, -1], [-1, -1], [-1, 1], // backward
];

function shuffled(arr) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }

function buildGrid(words) {
  const maxLen = Math.max(...words.map(w => w.length), 8);
  const size = Math.max(10, Math.min(16, maxLen + 4));
  const grid = Array.from({ length: size }, () => Array(size).fill(""));
  const placements = [];
  const sorted = [...words].sort((a, b) => b.length - a.length);

  function tryPlace(word) {
    const dirs = shuffled(DIRECTIONS);
    for (let attempt = 0; attempt < 120; attempt++) {
      const [dx, dy] = dirs[attempt % dirs.length];
      const maxStartX = dx === 0 ? size - 1 : dx > 0 ? size - word.length : word.length - 1;
      const maxStartY = dy === 0 ? size - 1 : dy > 0 ? size - word.length : word.length - 1;
      const minStartX = dx >= 0 ? 0 : word.length - 1;
      const minStartY = dy >= 0 ? 0 : word.length - 1;
      const sx = minStartX + Math.floor(Math.random() * (maxStartX - minStartX + 1));
      const sy = minStartY + Math.floor(Math.random() * (maxStartY - minStartY + 1));
      let ok = true;
      for (let i = 0; i < word.length; i++) {
        const x = sx + dx * i, y = sy + dy * i;
        if (x < 0 || x >= size || y < 0 || y >= size) { ok = false; break; }
        const ch = grid[y][x];
        if (ch && ch !== word[i]) { ok = false; break; }
      }
      if (!ok) continue;
      for (let i = 0; i < word.length; i++) {
        const x = sx + dx * i, y = sy + dy * i;
        grid[y][x] = word[i];
      }
      placements.push({ word, sx, sy, dx, dy });
      return true;
    }
    return false;
  }

  const placed = [];
  const failed = [];
  for (const w of sorted) {
    if (tryPlace(w)) placed.push(w); else failed.push(w);
  }
  // Fill empties with random letters
  const ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (!grid[y][x]) grid[y][x] = ALPHA[Math.floor(Math.random() * 26)];
    }
  }
  return { grid, size, placements, failed };
}

function stepBetween(start, end) {
  // Return array of cell coords if start→end form a straight 8-dir line, else null.
  const dx = end.x - start.x, dy = end.y - start.y;
  const ax = Math.abs(dx), ay = Math.abs(dy);
  let sx = 0, sy = 0;
  if (ax === 0 && ay === 0) return [{ x: start.x, y: start.y }];
  if (ax === 0) sy = dy > 0 ? 1 : -1;
  else if (ay === 0) sx = dx > 0 ? 1 : -1;
  else if (ax === ay) { sx = dx > 0 ? 1 : -1; sy = dy > 0 ? 1 : -1; }
  else return null; // not a straight line
  const len = Math.max(ax, ay) + 1;
  const out = [];
  for (let i = 0; i < len; i++) out.push({ x: start.x + sx * i, y: start.y + sy * i });
  return out;
}

function PlayWordSearch({ data }) {
  const words = data.words || [];
  const [{ grid, size }] = React.useState(() => buildGrid(words));
  const [found, setFound] = React.useState([]); // list of lowercased words
  const [foundCells, setFoundCells] = React.useState({}); // "x,y" -> true
  const [start, setStart] = React.useState(null);
  const [hover, setHover] = React.useState(null);
  const gridRef = React.useRef(null);

  function cellFromEvent(e) {
    const el = gridRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    const touch = e.touches && e.touches[0];
    const clientX = touch ? touch.clientX : e.clientX;
    const clientY = touch ? touch.clientY : e.clientY;
    if (clientX == null) return null;
    // Find target via elementFromPoint (works for mouse + touch)
    const target = document.elementFromPoint(clientX, clientY);
    if (!target) return null;
    const cell = target.closest(".ws-cell");
    if (!cell || !el.contains(cell)) return null;
    const x = Number(cell.dataset.x), y = Number(cell.dataset.y);
    if (Number.isNaN(x) || Number.isNaN(y)) return null;
    return { x, y };
  }

  function onDown(e) {
    const c = cellFromEvent(e);
    if (!c) return;
    e.preventDefault();
    setStart(c); setHover(c);
  }
  function onMove(e) {
    if (!start) return;
    const c = cellFromEvent(e);
    if (c) setHover(c);
  }
  function onUp() {
    if (!start || !hover) { setStart(null); setHover(null); return; }
    const cells = stepBetween(start, hover);
    if (cells) {
      const letters = cells.map(c => grid[c.y][c.x]).join("");
      const match = words.find(w =>
        !found.includes(w.toLowerCase()) &&
        (w === letters || w === letters.split("").reverse().join(""))
      );
      if (match) {
        setFound(f => [...f, match.toLowerCase()]);
        setFoundCells(fc => {
          const next = { ...fc };
          for (const c of cells) next[c.x + "," + c.y] = true;
          return next;
        });
      }
    }
    setStart(null); setHover(null);
  }

  const selected = start && hover ? (stepBetween(start, hover) || []) : [];
  const selectedKeys = new Set(selected.map(c => c.x + "," + c.y));

  const allFound = found.length === words.length;

  return (
    <div className="app">
      <h1>{data.title || "Word Search"}</h1>
      <div className="subtitle">Click and drag across letters to mark a word. Words can run in any of 8 directions.</div>
      <div className="ws-layout">
        <div className="ws-grid-wrap"
             onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}
             onTouchStart={onDown} onTouchMove={onMove} onTouchEnd={onUp}>
          <div ref={gridRef} className="ws-grid" style={{ gridTemplateColumns: `repeat(${size}, 34px)` }}>
            {grid.map((row, y) => row.map((ch, x) => {
              const key = x + "," + y;
              const isFound = foundCells[key];
              const isSel = selectedKeys.has(key);
              return (
                <div key={key} data-x={x} data-y={y}
                     className={"ws-cell" + (isFound ? " found" : "") + (isSel ? " sel" : "")}>
                  {ch}
                </div>
              );
            }))}
          </div>
        </div>
        <div className="ws-words">
          <h3>Find these words ({found.length}/{words.length})</h3>
          {words.map(w => (
            <div key={w} className={"ws-word" + (found.includes(w.toLowerCase()) ? " found" : "")}>
              {w}
            </div>
          ))}
        </div>
      </div>
      {allFound && (
        <div className="status good">✓ All {words.length} words found!</div>
      )}
      <div className="controls">
        <button className="btn btn-secondary" onClick={() => { setFound([]); setFoundCells({}); }}>Reset</button>
      </div>
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<PlayWordSearch data={DATA} />);
</script></body></html>
"""


def _build_html(data: dict) -> str:
    title = (data.get("title") or "Word Search").replace("<", "").replace(">", "")
    payload = json.dumps(data).replace("</", "<\\/")
    return _HTML.replace("__TITLE__", title).replace("__DATA_JSON__", payload)


def generate_wordsearch_activity(
    topic: str, grade: str, subject: str,
    teacher_id: str, class_id: str,
    standards: list | None = None,
    question_count: int = 12,
) -> dict:
    log.info(f"[WordSearch] topic='{topic[:60]}' grade={grade} subject={subject} count={question_count}")
    data = _generate_words(topic, grade, subject, standards, question_count)
    html = _build_html(data)
    return deploy_structured_activity(
        html=html,
        template_id="word_search",
        title=data.get("title", "Word Search"),
        teacher_id=teacher_id, class_id=class_id,
        standards=standards,
        content_summary={"topic": topic, "subject": subject, "grade": grade,
                         "word_count": len(data["words"])},
        full_data=data,
        questions_for_assignment=[{"word": w} for w in data["words"]],
    )
