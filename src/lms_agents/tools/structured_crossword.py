"""
Structured crossword activity generator.

Unlike artifact mode (where Gemini writes the full HTML + engine), this
module owns the crossword engine (layout algorithm + React component) and
asks Gemini ONLY for the puzzle data: words + clues. Zero runtime bugs from
LLM-written grid logic — the engine is deterministic code we control.

Public entry point: generate_crossword_activity(...)
"""
import json
import logging
import os
import re
from secrets import choice
import string
from uuid import uuid4

log = logging.getLogger(__name__)

CONTENT_MODEL = "gemini-3.1-pro-preview"


def _gemini_client():
    from google import genai
    api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def _generate_words(
    topic: str,
    grade: str,
    subject: str,
    standards: list[str] | None = None,
    target_count: int = 10,
    teacher_id: str | None = None,
) -> dict:
    """Ask Gemini for crossword-ready words + clues. Returns
    {title: str, words: [{answer: str, clue: str}]}."""
    standards_line = (
        f"\nAligned standards: {', '.join(standards)}" if standards else ""
    )
    from src.lms_agents.tools.structured_common import fetch_grounding_context
    grounding = fetch_grounding_context(
        topic=topic, grade=grade, subject=subject,
        standards=standards, teacher_id=teacher_id,
    )
    prompt = f"""You are designing a K-12 crossword puzzle.

TOPIC: {topic}
SUBJECT: {subject}
GRADE LEVEL: {grade}{standards_line}

{grounding}
Produce between 8 and {target_count} words, each with a short classroom clue.

RULES FOR EACH WORD:
- answer: single uppercase word, A-Z letters only (no spaces, no hyphens, no punctuation, no numbers)
- 3 to 10 letters long
- grade-appropriate vocabulary for grade {grade}
- directly related to the topic
- prefer answers that share letters so they interlock well (include at least a few common letters: A, E, I, O, N, R, S, T)

RULES FOR EACH CLUE:
- a single short sentence or phrase (under ~80 characters)
- NEVER contains the answer word or any word from the answer
- age-appropriate for grade {grade}

Output ONLY JSON, no markdown fences, no preamble:
{{
  "title": "<crossword title, max 60 chars>",
  "words": [
    {{"answer": "SUN", "clue": "The star at the center of our solar system."}},
    {{"answer": "ORBIT", "clue": "The path one object takes around another in space."}}
  ]
}}"""

    client = _gemini_client()
    resp = client.models.generate_content(
        model=CONTENT_MODEL,
        contents=[prompt],
    )
    text = (resp.text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"Gemini returned no JSON: {text[:300]}")
    data = json.loads(match.group())

    # Sanitize: uppercase, strip, drop invalid entries
    cleaned = []
    seen = set()
    for w in data.get("words", []) or []:
        if not isinstance(w, dict):
            continue
        ans = str(w.get("answer", "")).strip().upper()
        ans = re.sub(r"[^A-Z]", "", ans)
        clue = str(w.get("clue", "")).strip()
        if not ans or not clue:
            continue
        if len(ans) < 3 or len(ans) > 12:
            continue
        # Reject clues that contain the answer (data leakage)
        if ans.lower() in clue.lower():
            continue
        if ans in seen:
            continue
        seen.add(ans)
        cleaned.append({"answer": ans, "clue": clue})
    if len(cleaned) < 4:
        raise ValueError(f"Gemini returned only {len(cleaned)} usable words")
    # Cap at target_count
    cleaned = cleaned[:target_count]
    title = str(data.get("title", "") or "Crossword Puzzle").strip()[:80]
    return {"title": title, "words": cleaned}


def _generate_access_code(length: int = 6) -> str:
    return "".join(choice(string.ascii_uppercase + string.digits) for _ in range(length))


# ---------------------------------------------------------------------------
# HTML template — the crossword engine + React component. Gemini never sees
# this; we just inject the puzzle data as JSON. No brace-escaping gymnastics.
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__ — Lulia</title>
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'DM Sans', sans-serif; background: #F5DEC3; min-height: 100vh; padding: 24px; }
.app { max-width: 1000px; margin: 0 auto; background: #FEF9F2; border-radius: 20px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
h1 { font-family: 'DM Serif Display', serif; color: #F97316; font-size: 28px; margin-bottom: 4px; }
.subtitle { color: #78716C; font-size: 14px; margin-bottom: 20px; }
.xc-layout { display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-start; }
.xc-grid-wrap { position: relative; background: white; padding: 8px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); flex: 0 0 auto; }
.xc-cell, .xc-empty { position: absolute; box-sizing: border-box; }
.xc-empty { background: transparent; }
.xc-cell { background: white; border: 1px solid #D6D3D1; }
.xc-cell input { width: 100%; height: 100%; border: none; outline: none; text-align: center; font-size: 18px; font-weight: 600; color: #1C1917; background: transparent; text-transform: uppercase; font-family: 'DM Sans'; cursor: pointer; caret-color: transparent; padding: 0; }
.xc-cell.in-word { background: #FFEDD5; }
.xc-cell.selected { background: #FDBA74; }
.xc-cell.correct { background: #DCFCE7; border-color: #22C55E; }
.xc-cell.wrong { background: #FEE2E2; border-color: #EF4444; }
.xc-num { position: absolute; top: 1px; left: 2px; font-size: 9px; font-weight: 600; color: #78716C; line-height: 1; pointer-events: none; }
.xc-cell input.reveal { color: #DC2626; font-weight: 800; cursor: default; }
.xc-clues { flex: 1 1 300px; min-width: 260px; display: flex; flex-direction: column; gap: 10px; }
.xc-clue-group { background: white; border-radius: 10px; padding: 14px 16px; border: 1px solid #E7E5E4; }
.xc-clue-group h3 { font-family: 'DM Serif Display', serif; color: #78350F; font-size: 16px; margin-bottom: 8px; }
.xc-clue-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.xc-clue { cursor: pointer; padding: 6px 8px; border-radius: 6px; font-size: 13px; color: #1C1917; display: flex; gap: 8px; }
.xc-clue:hover { background: #FFF7ED; }
.xc-clue.active { background: #FFEDD5; font-weight: 600; }
.xc-clue .num { color: #F97316; font-weight: 700; flex: 0 0 auto; min-width: 20px; }
.xc-clue.solved { color: #16A34A; text-decoration: line-through; }
.xc-bank { background: white; border: 1px solid #E7E5E4; border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; }
.xc-bank-title { font-family: 'DM Serif Display', serif; color: #78350F; font-size: 14px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; }
.xc-bank-title .count { font-family: 'DM Sans'; font-size: 11px; color: #A8A29E; font-weight: 500; }
.xc-bank-words { display: flex; flex-wrap: wrap; gap: 6px; }
.xc-bank-word { font-family: monospace; font-size: 13px; font-weight: 600; padding: 4px 10px; border-radius: 999px; background: #FFEDD5; color: #7C2D12; letter-spacing: 0.05em; }
.xc-bank-word.solved { background: #DCFCE7; color: #15803D; text-decoration: line-through; }
.xc-controls { margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap; }
.btn-primary { background: #F97316; color: white; border: none; padding: 10px 22px; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: 'DM Sans'; }
.btn-primary:hover { background: #EA580C; }
.btn-secondary { background: white; color: #78350F; border: 1px solid #E7E5E4; padding: 10px 22px; border-radius: 10px; font-size: 14px; font-weight: 500; cursor: pointer; font-family: 'DM Sans'; }
.btn-secondary:hover { background: #FFF7ED; }
.status { margin-top: 16px; padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600; }
.status.success { background: #DCFCE7; color: #15803D; }
.status.partial { background: #FEF3C7; color: #A16207; }
.logo { text-align: center; font-size: 11px; color: #A8A29E; margin-top: 18px; }
.dropped { margin-top: 6px; font-size: 12px; color: #A8A29E; }
@media (max-width: 720px) {
  .xc-layout { flex-direction: column; }
  .xc-clues { width: 100%; }
}
</style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const PUZZLE = __PUZZLE_JSON__;

function layoutCrossword(words) {
  if (!words || words.length === 0) return { width: 1, height: 1, cells: {}, placed: [], dropped: [] };
  const sorted = [...words].sort((a, b) => b.answer.length - a.answer.length);
  const cells = new Map();
  const placed = [];
  const dropped = [];

  // Place first word horizontally at origin
  const first = sorted[0];
  for (let i = 0; i < first.answer.length; i++) cells.set(i + ",0", first.answer[i]);
  placed.push({ answer: first.answer, clue: first.clue, x: 0, y: 0, direction: "across" });

  function conflictsAt(x, y, letter) {
    const existing = cells.get(x + "," + y);
    return existing !== undefined && existing !== letter;
  }
  function neighborFilled(x, y) {
    return cells.has(x + "," + y);
  }

  for (let w = 1; w < sorted.length; w++) {
    const word = sorted[w];
    let placement = null;
    outer:
    for (const p of placed) {
      for (let i = 0; i < word.answer.length; i++) {
        for (let j = 0; j < p.answer.length; j++) {
          if (word.answer[i] !== p.answer[j]) continue;
          const newDir = p.direction === "across" ? "down" : "across";
          let sx, sy;
          if (p.direction === "across") { sx = p.x + j; sy = p.y - i; }
          else { sx = p.x - i; sy = p.y + j; }
          let ok = true;
          // body cells
          for (let k = 0; k < word.answer.length; k++) {
            const cx = newDir === "across" ? sx + k : sx;
            const cy = newDir === "down" ? sy + k : sy;
            if (conflictsAt(cx, cy, word.answer[k])) { ok = false; break; }
            // Adjacent cells perpendicular to word direction (no parallel touch)
            // Only enforce when the current cell is NEW (not the intersection)
            const isIntersection = (cx === (p.direction === "across" ? p.x + j : p.x))
                                   && (cy === (p.direction === "across" ? p.y : p.y + j));
            if (!isIntersection) {
              const sidePairs = newDir === "across"
                ? [[cx, cy - 1], [cx, cy + 1]]
                : [[cx - 1, cy], [cx + 1, cy]];
              for (const [nx, ny] of sidePairs) {
                if (neighborFilled(nx, ny)) { ok = false; break; }
              }
              if (!ok) break;
            }
          }
          // Before / after cells must be empty
          if (ok) {
            const beforeX = newDir === "across" ? sx - 1 : sx;
            const beforeY = newDir === "across" ? sy : sy - 1;
            const afterX = newDir === "across" ? sx + word.answer.length : sx;
            const afterY = newDir === "across" ? sy : sy + word.answer.length;
            if (neighborFilled(beforeX, beforeY) || neighborFilled(afterX, afterY)) ok = false;
          }
          if (ok) { placement = { x: sx, y: sy, direction: newDir }; break outer; }
        }
      }
    }
    if (placement) {
      for (let k = 0; k < word.answer.length; k++) {
        const cx = placement.direction === "across" ? placement.x + k : placement.x;
        const cy = placement.direction === "down" ? placement.y + k : placement.y;
        cells.set(cx + "," + cy, word.answer[k]);
      }
      placed.push({ answer: word.answer, clue: word.clue, x: placement.x, y: placement.y, direction: placement.direction });
    } else {
      dropped.push(word);
    }
  }

  // Normalize coordinates
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const key of cells.keys()) {
    const [x, y] = key.split(",").map(Number);
    if (x < minX) minX = x; if (y < minY) minY = y;
    if (x > maxX) maxX = x; if (y > maxY) maxY = y;
  }
  const shifted = {};
  for (const [key, val] of cells) {
    const [x, y] = key.split(",").map(Number);
    shifted[(x - minX) + "," + (y - minY)] = val;
  }
  const shiftedPlaced = placed.map(p => ({ ...p, x: p.x - minX, y: p.y - minY }));
  const width = maxX - minX + 1;
  const height = maxY - minY + 1;

  // Assign clue numbers in reading order (top-to-bottom, left-to-right)
  const startKeys = new Set(shiftedPlaced.map(p => p.x + "," + p.y));
  const orderedStarts = [];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (startKeys.has(x + "," + y)) orderedStarts.push(x + "," + y);
    }
  }
  const startNumbers = {};
  orderedStarts.forEach((key, idx) => { startNumbers[key] = idx + 1; });
  for (const p of shiftedPlaced) p.number = startNumbers[p.x + "," + p.y];

  return { width, height, cells: shifted, placed: shiftedPlaced, startNumbers, dropped };
}

function PlayCrossword({ data }) {
  const title = data.title || "Crossword Puzzle";
  const words = data.words || [];
  const layout = React.useMemo(() => layoutCrossword(words), [words]);
  const [typed, setTyped] = React.useState({});
  const [selected, setSelected] = React.useState(null);
  const [direction, setDirection] = React.useState("across");
  const [showResult, setShowResult] = React.useState(false);
  const inputRefs = React.useRef({});

  // Select the first cell on mount (best-effort — avoid crashing on empty grid)
  React.useEffect(() => {
    const first = layout.placed[0];
    if (first) { setSelected({ x: first.x, y: first.y }); setDirection(first.direction); }
  }, [layout]);

  function wordAt(x, y, dir) {
    return layout.placed.find(p => {
      if (p.direction !== dir) return false;
      if (dir === "across") return p.y === y && x >= p.x && x < p.x + p.answer.length;
      return p.x === x && y >= p.y && y < p.y + p.answer.length;
    });
  }

  const currentWord = selected ? (wordAt(selected.x, selected.y, direction)
    || wordAt(selected.x, selected.y, direction === "across" ? "down" : "across")) : null;

  function cellsOfWord(w) {
    const arr = [];
    for (let k = 0; k < w.answer.length; k++) {
      arr.push({ x: w.direction === "across" ? w.x + k : w.x,
                 y: w.direction === "down" ? w.y + k : w.y });
    }
    return arr;
  }

  function focusCell(x, y) {
    const ref = inputRefs.current[x + "," + y];
    if (ref) setTimeout(() => ref.focus(), 0);
  }

  function onCellClick(x, y) {
    if (selected && selected.x === x && selected.y === y) {
      setDirection(d => d === "across" ? "down" : "across");
    } else {
      setSelected({ x, y });
      // Auto-pick direction: if a word runs across through here, prefer across
      const across = wordAt(x, y, "across");
      const down = wordAt(x, y, "down");
      if (across && !down) setDirection("across");
      else if (down && !across) setDirection("down");
    }
    focusCell(x, y);
  }

  function onCellChange(x, y, val) {
    const raw = String(val || "").toUpperCase();
    const letter = raw.replace(/[^A-Z]/g, "").slice(-1);
    setTyped(t => ({ ...t, [x + "," + y]: letter }));
    if (letter && currentWord) {
      const nx = currentWord.direction === "across" ? x + 1 : x;
      const ny = currentWord.direction === "down" ? y + 1 : y;
      if (layout.cells[nx + "," + ny]) { setSelected({ x: nx, y: ny }); focusCell(nx, ny); }
    }
  }

  function onKeyDown(e, x, y) {
    const k = e.key;
    if (k === "Backspace") {
      if (!typed[x + "," + y] && currentWord) {
        e.preventDefault();
        const px = currentWord.direction === "across" ? x - 1 : x;
        const py = currentWord.direction === "down" ? y - 1 : y;
        if (layout.cells[px + "," + py]) { setSelected({ x: px, y: py }); focusCell(px, py); }
      }
    } else if (k === "ArrowLeft" || k === "ArrowRight" || k === "ArrowUp" || k === "ArrowDown") {
      e.preventDefault();
      const dx = k === "ArrowLeft" ? -1 : k === "ArrowRight" ? 1 : 0;
      const dy = k === "ArrowUp" ? -1 : k === "ArrowDown" ? 1 : 0;
      const nx = x + dx, ny = y + dy;
      if (layout.cells[nx + "," + ny]) {
        setSelected({ x: nx, y: ny });
        setDirection(dx !== 0 ? "across" : "down");
        focusCell(nx, ny);
      }
    } else if (k === " " || k === "Tab") {
      e.preventDefault();
      setDirection(d => d === "across" ? "down" : "across");
    } else if (k.length === 1 && /[a-zA-Z]/.test(k)) {
      // Handle letter input in onKeyDown (not onChange) because controlled
      // <input maxLength=1> does NOT fire onChange when the typed character
      // equals the existing value — that meant intersecting cells blocked
      // progress through shared letters (e.g. typing "S" over an "S" from
      // another solved word). This always advances.
      e.preventDefault();
      const letter = k.toUpperCase();
      setTyped(t => ({ ...t, [x + "," + y]: letter }));
      if (currentWord) {
        const nx = currentWord.direction === "across" ? x + 1 : x;
        const ny = currentWord.direction === "down" ? y + 1 : y;
        if (layout.cells[nx + "," + ny]) { setSelected({ x: nx, y: ny }); focusCell(nx, ny); }
      }
    }
  }

  function jumpToClue(p) {
    setSelected({ x: p.x, y: p.y });
    setDirection(p.direction);
    focusCell(p.x, p.y);
  }

  function wordIsSolved(p) {
    for (let k = 0; k < p.answer.length; k++) {
      const cx = p.direction === "across" ? p.x + k : p.x;
      const cy = p.direction === "down" ? p.y + k : p.y;
      if ((typed[cx + "," + cy] || "") !== p.answer[k]) return false;
    }
    return true;
  }

  function checkAnswers() { setShowResult(true); }
  function clearGrid() { setTyped({}); setShowResult(false); }

  const cellSize = 40;
  const cellsJSX = [];
  for (let y = 0; y < layout.height; y++) {
    for (let x = 0; x < layout.width; x++) {
      const key = x + "," + y;
      const expected = layout.cells[key];
      if (!expected) {
        cellsJSX.push(<div key={key} className="xc-empty" style={{ left: x * cellSize, top: y * cellSize, width: cellSize, height: cellSize }} />);
        continue;
      }
      const ch = typed[key] || "";
      const isSel = selected && selected.x === x && selected.y === y;
      const isInWord = currentWord && cellsOfWord(currentWord).some(c => c.x === x && c.y === y);
      const correct = showResult && ch === expected;
      const wrong = showResult && ch && ch !== expected;
      const empty = showResult && !ch;
      const cls = ["xc-cell",
        isSel ? "selected" : (isInWord ? "in-word" : ""),
        correct ? "correct" : "",
        wrong ? "wrong" : "",
        empty ? "wrong" : ""].filter(Boolean).join(" ");
      const num = layout.startNumbers[key];
      const showAnswer = showResult && ch !== expected;
      const displayValue = showAnswer ? expected : ch;
      cellsJSX.push(
        <div key={key} className={cls} style={{ left: x * cellSize, top: y * cellSize, width: cellSize, height: cellSize }}>
          {num && <span className="xc-num">{num}</span>}
          <input
            ref={el => { inputRefs.current[key] = el; }}
            value={displayValue}
            className={showAnswer ? "reveal" : ""}
            readOnly={showAnswer}
            onChange={e => onCellChange(x, y, e.target.value)}
            onKeyDown={e => onKeyDown(e, x, y)}
            onClick={() => onCellClick(x, y)}
            maxLength={1}
            inputMode="text"
            aria-label={"Cell " + (num ? num + " " : "") + (x + 1) + "," + (y + 1)}
          />
        </div>
      );
    }
  }

  const across = layout.placed.filter(p => p.direction === "across").sort((a, b) => a.number - b.number);
  const down = layout.placed.filter(p => p.direction === "down").sort((a, b) => a.number - b.number);

  const solvedCount = layout.placed.filter(wordIsSolved).length;
  const allCorrect = showResult && solvedCount === layout.placed.length;

  // Word bank — shuffled once on mount so students don't get alphabetical hints
  const showBank = !!data.word_bank;
  const [bankWords] = React.useState(() => {
    if (!showBank) return [];
    const arr = layout.placed.map(p => p.answer);
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  });

  return (
    <div className="app">
      <h1>{title}</h1>
      <div className="subtitle">Tap a cell or clue to start. Tap the same cell again to switch direction.</div>
      {showBank && bankWords.length > 0 && (
        <div className="xc-bank">
          <div className="xc-bank-title">
            <span>Word bank</span>
            <span className="count">{solvedCount} / {layout.placed.length} found</span>
          </div>
          <div className="xc-bank-words">
            {bankWords.map(w => {
              const done = layout.placed.find(p => p.answer === w && wordIsSolved(p));
              return (
                <span key={w} className={"xc-bank-word" + (done ? " solved" : "")}>
                  {w}
                </span>
              );
            })}
          </div>
        </div>
      )}
      <div className="xc-layout">
        <div className="xc-grid-wrap" style={{ width: layout.width * cellSize, height: layout.height * cellSize }}>
          {cellsJSX}
        </div>
        <div className="xc-clues">
          <div className="xc-clue-group">
            <h3>Across</h3>
            <ul className="xc-clue-list">
              {across.map(p => (
                <li key={"a" + p.number}
                    className={"xc-clue" + (currentWord === p ? " active" : "") + (showResult && wordIsSolved(p) ? " solved" : "")}
                    onClick={() => jumpToClue(p)}>
                  <span className="num">{p.number}.</span><span>{p.clue}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="xc-clue-group">
            <h3>Down</h3>
            <ul className="xc-clue-list">
              {down.map(p => (
                <li key={"d" + p.number}
                    className={"xc-clue" + (currentWord === p ? " active" : "") + (showResult && wordIsSolved(p) ? " solved" : "")}
                    onClick={() => jumpToClue(p)}>
                  <span className="num">{p.number}.</span><span>{p.clue}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
      <div className="xc-controls">
        <button className="btn-primary" onClick={checkAnswers}>Check answers</button>
        <button className="btn-secondary" onClick={clearGrid}>Clear</button>
      </div>
      {showResult && (
        <div className={"status " + (allCorrect ? "success" : "partial")}>
          {allCorrect ? "✓ Perfect — all " + layout.placed.length + " words solved!" :
           solvedCount + " of " + layout.placed.length + " words correct."}
        </div>
      )}
      {layout.dropped && layout.dropped.length > 0 && (
        <div className="dropped">({layout.dropped.length} extra word{layout.dropped.length > 1 ? "s" : ""} couldn't be placed in this grid layout.)</div>
      )}
      <div className="logo">Powered by Lulia AI</div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<PlayCrossword data={PUZZLE} />);
</script>
</body>
</html>
"""


def _build_crossword_html(data: dict) -> str:
    """Inject puzzle data into the HTML template."""
    title = (data.get("title") or "Crossword Puzzle").replace("<", "").replace(">", "")
    puzzle_json = json.dumps(data)
    html = _HTML_TEMPLATE.replace("__TITLE__", title)
    # Use a JSON-safe substitution that also escapes </script> if it ever appears
    puzzle_json_safe = puzzle_json.replace("</", "<\\/")
    html = html.replace("__PUZZLE_JSON__", puzzle_json_safe)
    return html


def _deploy_activity(
    html: str,
    teacher_id: str,
    class_id: str,
    standards: list | None,
    data: dict,
    topic: str,
    subject: str,
    grade: str,
) -> dict:
    """Upload HTML to MinIO and persist assignment + activity rows."""
    import boto3
    from psycopg2.extras import Json
    from src.lms_agents.tools.db import get_connection

    assignment_id = str(uuid4())
    activity_id = str(uuid4())
    access_code = _generate_access_code()

    # 1. Assignment row (FK target for the interactive activity)
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO assignments
               (assignment_id, class_id, teacher_id, title,
                output_template_id, output_format, design_theme,
                standards_ids, questions, answer_key, qa_report,
                status, file_paths)
               VALUES (%s, %s::uuid, %s::uuid, %s,
                       %s, %s, %s,
                       %s, %s, %s, %s,
                       'complete', %s)""",
            (
                assignment_id, class_id, teacher_id,
                data.get("title", "Crossword"),
                "crossword", "interactive_structured", "lulia_default",
                Json(standards or []),
                Json(data.get("words", [])),
                Json({}),
                Json({"approved": True, "source": "structured_crossword"}),
                Json({"note": "structured crossword"}),
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # 2. Upload HTML to MinIO
    s3 = boto3.client(
        "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )
    bucket = os.environ.get("S3_BUCKET_ACTIVITIES", "lulia-activities")
    key = f"activities/{activity_id}/index.html"
    s3.put_object(Bucket=bucket, Key=key, Body=html.encode("utf-8"),
                  ContentType="text/html; charset=utf-8")
    endpoint = os.environ.get("S3_PUBLIC_ENDPOINT") or os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    access_url = f"{endpoint}/{bucket}/{key}"

    # 3. interactive_activities row
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO interactive_activities
               (activity_id, assignment_id, teacher_id, class_id,
                interactive_template_id, content_json, access_code, access_url,
                max_attempts, time_limit_seconds, show_answers_after, status)
               VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'live')""",
            (
                activity_id, assignment_id, teacher_id, class_id,
                "crossword",
                Json({"mode": "structured", "template": "crossword", "topic": topic,
                      "subject": subject, "grade": grade,
                      "words_count": len(data.get("words", [])),
                      "data": data}),
                access_code, access_url,
                3, None, True,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    log.info(f"[Crossword] Deployed to {access_url}")
    return {
        "activity_id": activity_id,
        "assignment_id": assignment_id,
        "access_code": access_code,
        "access_url": access_url,
        "template": "crossword",
        "mode": "structured",
        "status": "live",
        "word_count": len(data.get("words", [])),
    }


def generate_crossword_activity(
    topic: str,
    grade: str,
    subject: str,
    teacher_id: str,
    class_id: str,
    standards: list | None = None,
    question_count: int = 10,
) -> dict:
    """End-to-end structured crossword generation.

    Gemini produces only the DATA (words + clues). This module owns the
    engine (layout algorithm + React component) so there's no LLM-written
    JS that can crash at runtime.
    """
    log.info(f"[Crossword] topic='{topic[:60]}' grade={grade} subject={subject} count={question_count}")
    data = _generate_words(
        topic=topic, grade=grade, subject=subject,
        standards=standards, target_count=question_count,
        teacher_id=teacher_id,
    )
    html = _build_crossword_html(data)
    return _deploy_activity(
        html=html, teacher_id=teacher_id, class_id=class_id,
        standards=standards, data=data, topic=topic, subject=subject, grade=grade,
    )
