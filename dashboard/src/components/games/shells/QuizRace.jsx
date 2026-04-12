'use client';
import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, Clock, Users, Trophy } from 'lucide-react';

/**
 * Quiz Race shell — Kahoot-style MC.
 *
 * Renders the current question + 4 answer choices. Student taps one; we report
 * back through onAnswer() and show a correct/wrong flash. Teacher-view variant
 * shows the same question with a per-player answered-count pill instead of the
 * answer buttons.
 *
 * Props:
 *   question: { question_text, options, answer (teacher view only) }
 *   players: [{player_id, name, avatar, score}]
 *   view: 'student' | 'teacher'
 *   onAnswer: (answer) => void
 *   config: { timer_seconds }
 *   questionIndex, totalQuestions
 *   lastResult: { correct, points, correct_answer } | null  (student only)
 */
export default function QuizRace({
  question, players = [], view = 'student', onAnswer, config = {},
  questionIndex = 0, totalQuestions = 1, lastResult = null,
}) {
  const timer = config.timer_seconds || 20;
  const [remaining, setRemaining] = useState(timer);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    setSelected(null);
    setRemaining(timer);
  }, [question?.question_text, timer]);

  useEffect(() => {
    if (!timer || remaining <= 0) return;
    const t = setTimeout(() => setRemaining(r => r - 1), 1000);
    return () => clearTimeout(t);
  }, [remaining, timer]);

  if (!question) {
    return (
      <div className="rounded-card p-10 text-center" style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <p className="font-serif text-[20px]" style={{ color: 'var(--text-mid)' }}>
          Waiting for the next question…
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-[12px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
          Question {questionIndex + 1} of {totalQuestions}
        </span>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1 text-[13px] font-bold" style={{ color: 'var(--text-mid)' }}>
            <Users className="w-4 h-4" /> {players.length}
          </span>
          {timer > 0 && (
            <span className="flex items-center gap-1 text-[13px] font-bold"
              style={{ color: remaining <= 5 ? 'var(--coral)' : 'var(--sage)' }}>
              <Clock className="w-4 h-4" /> {remaining}s
            </span>
          )}
        </div>
      </div>

      {/* Question card */}
      <div className="rounded-card p-6 mb-4"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)', boxShadow: '0 4px 14px rgba(60,40,20,0.06)' }}>
        <h2 className="font-serif text-[24px] text-center" style={{ color: 'var(--text-dark)' }}>
          {question.question_text}
        </h2>
      </div>

      {/* Answer choices (student) or player grid (teacher) */}
      {view === 'student' ? (
        <div className="grid grid-cols-2 gap-3">
          {(question.options || []).map((opt, i) => {
            const isSel = selected === opt;
            const correct = lastResult?.correct_answer === opt;
            const wrongSel = lastResult && isSel && !lastResult.correct;
            const revealed = !!lastResult;
            const colors = ['#D86C52', '#6BA08A', '#4E8C96', '#E9B44C']; // coral, sage, teal, mustard
            return (
              <button key={i}
                disabled={!!selected || remaining <= 0}
                onClick={() => { setSelected(opt); onAnswer?.(opt); }}
                className="rounded-card p-4 text-left font-bold text-[15px] transition-all disabled:cursor-not-allowed"
                style={{
                  background: revealed
                    ? (correct ? 'rgba(22,163,74,0.15)' : wrongSel ? 'rgba(239,68,68,0.12)' : 'var(--cream)')
                    : isSel ? `${colors[i]}20` : colors[i],
                  color: revealed ? 'var(--text-dark)' : 'white',
                  border: `2px solid ${revealed && correct ? '#16A34A' : revealed && wrongSel ? '#EF4444' : isSel ? colors[i] : 'transparent'}`,
                  opacity: revealed && !correct && !wrongSel ? 0.5 : 1,
                  cursor: selected ? 'default' : 'pointer',
                }}>
                <span className="inline-block w-6 h-6 rounded-full text-center text-[12px] leading-6 mr-2"
                  style={{ background: revealed ? colors[i] : 'rgba(255,255,255,0.25)', color: 'white' }}>
                  {String.fromCharCode(65 + i)}
                </span>
                {opt}
                {revealed && correct && <CheckCircle className="inline w-4 h-4 ml-2" style={{ color: '#16A34A' }} />}
                {revealed && wrongSel && <XCircle className="inline w-4 h-4 ml-2" style={{ color: '#EF4444' }} />}
              </button>
            );
          })}
        </div>
      ) : (
        <div>
          <div className="rounded-card p-4 mb-3"
            style={{ background: 'rgba(107,160,138,0.08)', border: '1px solid var(--sage)' }}>
            <p className="text-[12px] font-bold" style={{ color: 'var(--sage)' }}>
              Correct answer: {question.answer}
            </p>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {players.map(p => (
              <div key={p.player_id} className="rounded-xl p-2 text-center"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                <div className="text-[18px]">{p.avatar || '🐻'}</div>
                <div className="text-[11px] font-bold truncate" style={{ color: 'var(--text-dark)' }}>{p.name}</div>
                <div className="text-[10px]" style={{ color: 'var(--coral)' }}>{p.score || 0}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Student's result feedback */}
      {view === 'student' && lastResult && (
        <div className="mt-4 rounded-card p-3 text-center"
          style={{
            background: lastResult.correct ? 'rgba(22,163,74,0.1)' : 'rgba(239,68,68,0.08)',
            border: `1px solid ${lastResult.correct ? '#16A34A' : '#EF4444'}`,
          }}>
          {lastResult.correct ? (
            <span className="font-bold" style={{ color: '#16A34A' }}>
              <Trophy className="inline w-5 h-5 mr-1" /> Correct! +{lastResult.points} pts
            </span>
          ) : (
            <span className="font-bold" style={{ color: '#B91C1C' }}>
              Not quite. Correct answer: <strong>{lastResult.correct_answer}</strong>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
