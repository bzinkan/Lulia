'use client';
import { useEffect, useMemo, useState } from 'react';
import { CheckCircle, Trophy } from 'lucide-react';

/**
 * Bingo Blitz shell.
 *
 * Students get a randomized N×N card of answer terms. Teacher calls a question
 * (via the teacher control screen); students mark the cell that matches.
 * First to get a row/column/diagonal wins.
 *
 * Props:
 *   allQuestions: [{ question_text, answer, options }]
 *   question: current teacher-called question
 *   view: 'student' | 'teacher'
 *   config: { board_size: 3|4|5, free_space: bool, timer_seconds }
 *   playerId: stable id for this student so their card is reproducible
 *   onBingo: () => void  — student shouts bingo
 *   onCallNext: () => void  — teacher advances to next call
 *   calledAnswers: set of answers already called (strings)
 */
export default function BingoBlitz({
  allQuestions = [], question, view = 'student', config = {},
  playerId = 'anon', onBingo, onCallNext, calledAnswers = [],
}) {
  const size = config.board_size || 5;
  const freeSpace = config.free_space !== false;

  // Build a deterministic card per player (same seed = same card)
  const card = useMemo(() => {
    const answers = allQuestions.map(q => q.answer).filter(Boolean);
    const total = size * size;
    const shuffled = seededShuffle([...answers], playerId).slice(0, total);
    while (shuffled.length < total) shuffled.push('');
    const grid = [];
    for (let r = 0; r < size; r++) {
      grid.push(shuffled.slice(r * size, (r + 1) * size));
    }
    // Optional free space at center for odd sizes
    if (freeSpace && size % 2 === 1) {
      const mid = Math.floor(size / 2);
      grid[mid][mid] = 'FREE';
    }
    return grid;
  }, [allQuestions, size, freeSpace, playerId]);

  const [marked, setMarked] = useState(() => new Set(freeSpace && size % 2 === 1 ? ['FREE'] : []));
  const [hasWon, setHasWon] = useState(false);

  useEffect(() => {
    if (hasWon) return;
    // Check for bingo after each mark
    if (checkBingo(card, marked, size)) {
      setHasWon(true);
      onBingo?.();
    }
  }, [marked, card, size, hasWon, onBingo]);

  function toggleCell(term) {
    if (!term) return;
    // Only allow marking called answers (or FREE)
    if (term !== 'FREE' && !calledAnswers.includes(term)) return;
    const next = new Set(marked);
    if (next.has(term)) next.delete(term);
    else next.add(term);
    setMarked(next);
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-serif text-[22px]" style={{ color: 'var(--text-dark)' }}>
          Bingo Blitz
        </h2>
        <span className="text-[11px] font-bold px-2 py-1 rounded-full" style={{ background: 'var(--cream)', color: 'var(--text-mid)' }}>
          {size}×{size} · {calledAnswers.length} called
        </span>
      </div>

      {/* Called question panel (teacher + student both see it) */}
      {question && (
        <div className="rounded-card p-5 mb-4 text-center"
          style={{ background: 'var(--warm-card)', border: '2px solid var(--coral)' }}>
          <p className="text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--coral)' }}>
            Teacher asks
          </p>
          <p className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
            {question.question_text}
          </p>
          {view === 'teacher' && (
            <div className="mt-3 flex items-center justify-center gap-3">
              <span className="text-[11px] px-3 py-1 rounded-full"
                style={{ background: 'rgba(107,160,138,0.1)', color: 'var(--sage)' }}>
                Answer: <strong>{question.answer}</strong>
              </span>
              <button onClick={onCallNext}
                className="text-[12px] font-bold px-4 py-1.5 rounded-lg text-white"
                style={{ background: 'var(--coral)', cursor: 'pointer' }}>
                Call Next
              </button>
            </div>
          )}
        </div>
      )}

      {/* Student's card */}
      {view === 'student' && (
        <>
          <div className="grid gap-1.5 mb-3"
            style={{ gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))` }}>
            {card.flat().map((term, i) => {
              const isMarked = marked.has(term);
              const isCalled = term === 'FREE' || calledAnswers.includes(term);
              const isFree = term === 'FREE';
              return (
                <button key={i} onClick={() => toggleCell(term)}
                  disabled={!isCalled}
                  className="aspect-square rounded-xl p-2 text-[11px] font-bold flex items-center justify-center text-center leading-tight"
                  style={{
                    background: isMarked
                      ? (isFree ? 'var(--mustard, #E9B44C)' : 'rgba(107,160,138,0.3)')
                      : isCalled ? 'rgba(216,108,82,0.08)' : 'var(--warm-card)',
                    border: `2px solid ${isMarked ? 'var(--sage)' : isCalled ? 'var(--coral)' : 'var(--border)'}`,
                    color: isMarked ? 'var(--text-dark)' : 'var(--text-mid)',
                    cursor: isCalled ? 'pointer' : 'not-allowed',
                    opacity: isCalled ? 1 : 0.7,
                  }}>
                  {isFree ? '★ FREE' : (term || '—')}
                  {isMarked && !isFree && <CheckCircle className="w-3 h-3 ml-0.5" style={{ color: 'var(--sage)' }} />}
                </button>
              );
            })}
          </div>
          {hasWon && (
            <div className="rounded-card p-4 text-center"
              style={{ background: 'linear-gradient(135deg, var(--mustard, #E9B44C), #F5C866)', color: 'white' }}>
              <Trophy className="inline w-6 h-6 mr-1" />
              <span className="font-serif text-[22px] font-bold">BINGO!</span>
            </div>
          )}
        </>
      )}

      {/* Called answer list (teacher monitor) */}
      {view === 'teacher' && (
        <div className="rounded-card p-4"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
          <h3 className="text-[11px] font-bold uppercase mb-2 tracking-wider" style={{ color: 'var(--text-light)' }}>
            Called answers
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {calledAnswers.length === 0 ? (
              <p className="text-[12px]" style={{ color: 'var(--text-light)' }}>None yet.</p>
            ) : calledAnswers.map((a, i) => (
              <span key={i} className="text-[11px] font-semibold px-2 py-1 rounded-full"
                style={{ background: 'var(--cream)', color: 'var(--coral)', border: '1px solid var(--border)' }}>
                {a}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function seededShuffle(arr, seed) {
  // Simple FNV-1a based deterministic shuffle so each player gets a consistent card
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const rng = () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function checkBingo(card, marked, size) {
  // Rows
  for (let r = 0; r < size; r++) {
    if (card[r].every(c => marked.has(c))) return true;
  }
  // Columns
  for (let c = 0; c < size; c++) {
    if (card.every(row => marked.has(row[c]))) return true;
  }
  // Diagonals
  if (card.every((row, i) => marked.has(row[i]))) return true;
  if (card.every((row, i) => marked.has(row[size - 1 - i]))) return true;
  return false;
}
