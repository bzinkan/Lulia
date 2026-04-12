'use client';
import { useState, useEffect, useMemo } from 'react';
import { CheckCircle, XCircle } from 'lucide-react';

/**
 * Jeopardy shell — 5x5 category board.
 *
 * Each cell = one question. Teacher view shows the board; clicking a cell opens
 * the question for all students. Students see the board + current question.
 * Cells already answered are grayed out.
 *
 * Board layout: questions are divided evenly into 5 categories (round-robin).
 * Category names come from config.categories (comma-separated).
 */
const VALUES = [100, 200, 300, 400, 500];

export default function Jeopardy({
  question, players = [], view = 'student', onAnswer, onPickCell,
  config = {}, questionIndex = 0, totalQuestions = 25, answeredCells = [],
  allQuestions = [], lastResult = null,
}) {
  const categories = (config.categories || 'Vocab, Facts, Events, People, Dates')
    .split(',').map(c => c.trim()).slice(0, 5);
  while (categories.length < 5) categories.push(`Category ${categories.length + 1}`);

  // Build the 5x5 board: 5 columns (categories), 5 rows (values)
  const board = useMemo(() => {
    const grid = Array(5).fill(0).map(() => Array(5).fill(null));
    (allQuestions || []).slice(0, 25).forEach((q, idx) => {
      const col = idx % 5;
      const row = Math.floor(idx / 5);
      if (row < 5 && col < 5) grid[row][col] = { ...q, index: idx, value: VALUES[row] };
    });
    return grid;
  }, [allQuestions]);

  const [selected, setSelected] = useState(null);
  useEffect(() => { setSelected(null); }, [question?.question_text]);

  return (
    <div className="max-w-4xl mx-auto">
      {/* Category headers */}
      <div className="grid grid-cols-5 gap-2 mb-2">
        {categories.map((cat, i) => (
          <div key={i} className="rounded-xl py-3 text-center font-serif text-[15px]"
            style={{
              background: 'linear-gradient(135deg, var(--coral), var(--coral-light))',
              color: 'white',
              boxShadow: '0 2px 8px rgba(216,108,82,0.25)',
            }}>
            {cat}
          </div>
        ))}
      </div>

      {/* 5x5 board */}
      <div className="grid grid-cols-5 gap-2 mb-4">
        {board.flat().map((cell, i) => {
          const isAnswered = cell && answeredCells.includes(cell.index);
          const isCurrent = cell && questionIndex === cell.index;
          const clickable = view === 'teacher' && !isAnswered && cell;
          return (
            <button key={i}
              onClick={() => clickable && onPickCell?.(cell.index)}
              disabled={!clickable}
              className="aspect-video rounded-xl text-center font-serif text-[22px] font-bold transition-all"
              style={{
                background: isCurrent
                  ? 'var(--mustard, #E9B44C)'
                  : isAnswered
                    ? 'var(--cream)'
                    : 'var(--warm-card)',
                color: isAnswered
                  ? 'var(--text-light)'
                  : isCurrent
                    ? 'white'
                    : 'var(--coral)',
                border: `1px solid ${isCurrent ? 'var(--mustard, #E9B44C)' : 'var(--border)'}`,
                opacity: isAnswered ? 0.4 : 1,
                cursor: clickable ? 'pointer' : 'default',
                boxShadow: isCurrent ? '0 4px 14px rgba(233,180,76,0.3)' : 'none',
              }}>
              {cell ? (isAnswered ? '✓' : `$${cell.value}`) : '—'}
            </button>
          );
        })}
      </div>

      {/* Current question */}
      {question && (
        <div className="rounded-card p-6 mb-4"
          style={{ background: 'var(--warm-card)', border: '2px solid var(--coral)' }}>
          <p className="text-[11px] font-bold uppercase tracking-wider mb-2 text-center" style={{ color: 'var(--coral)' }}>
            {categories[questionIndex % 5]} · ${VALUES[Math.floor(questionIndex / 5)] || 100}
          </p>
          <h2 className="font-serif text-[22px] text-center mb-4" style={{ color: 'var(--text-dark)' }}>
            {question.question_text}
          </h2>
          {view === 'student' && (
            <div className="grid grid-cols-2 gap-3">
              {(question.options || []).map((opt, i) => {
                const isSel = selected === opt;
                return (
                  <button key={i}
                    disabled={!!selected}
                    onClick={() => { setSelected(opt); onAnswer?.(opt); }}
                    className="rounded-xl p-3 text-left font-semibold text-[14px]"
                    style={{
                      background: isSel ? 'rgba(216,108,82,0.1)' : 'var(--cream)',
                      border: `2px solid ${isSel ? 'var(--coral)' : 'var(--border)'}`,
                      color: 'var(--text-dark)',
                      cursor: selected ? 'default' : 'pointer',
                    }}>
                    <strong style={{ color: 'var(--coral)' }}>{String.fromCharCode(65 + i)}.</strong> {opt}
                  </button>
                );
              })}
            </div>
          )}
          {view === 'teacher' && (
            <div className="text-center">
              <span className="text-[12px] px-3 py-1 rounded-full font-bold"
                style={{ background: 'rgba(107,160,138,0.1)', color: 'var(--sage)' }}>
                Answer: {question.answer}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Student result */}
      {view === 'student' && lastResult && (
        <div className="rounded-card p-3 text-center"
          style={{
            background: lastResult.correct ? 'rgba(22,163,74,0.1)' : 'rgba(239,68,68,0.08)',
            border: `1px solid ${lastResult.correct ? '#16A34A' : '#EF4444'}`,
          }}>
          {lastResult.correct ? <CheckCircle className="inline w-5 h-5 mr-1" style={{ color: '#16A34A' }} /> : <XCircle className="inline w-5 h-5 mr-1" style={{ color: '#EF4444' }} />}
          <span className="font-bold" style={{ color: lastResult.correct ? '#16A34A' : '#B91C1C' }}>
            {lastResult.correct ? `Correct! +${lastResult.points}` : `Correct: ${lastResult.correct_answer}`}
          </span>
        </div>
      )}

      {/* Leaderboard strip (teacher) */}
      {view === 'teacher' && players.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {[...players].sort((a,b) => (b.score||0) - (a.score||0)).slice(0, 8).map(p => (
            <div key={p.player_id} className="rounded-xl px-3 py-1.5 flex items-center gap-2"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
              <span>{p.avatar || '🐻'}</span>
              <span className="text-[11px] font-bold" style={{ color: 'var(--text-dark)' }}>{p.name}</span>
              <span className="text-[11px] font-bold" style={{ color: 'var(--coral)' }}>${p.score || 0}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
