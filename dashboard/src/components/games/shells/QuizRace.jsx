'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, Clock, Users, Trophy, Volume2, VolumeX, Flame } from 'lucide-react';
import { play, setMuted, isMuted } from '@/lib/gameSounds';
import { correctAnswer } from '@/lib/confetti';

/**
 * Quiz Race — Kahoot-style MC with full polish:
 *   - Framer Motion staggered entrances, spring feedback, shake on wrong
 *   - Synthesized sound effects (Web Audio, no external files)
 *   - Confetti on correct answers
 *   - Circular countdown ring with urgent ticking at ≤5s
 *   - Animated score counter on update
 *   - Dual view: student (big tiles), teacher (answer reveal + player grid)
 */

const TILE_COLORS = ['#D86C52', '#6BA08A', '#4E8C96', '#E9B44C']; // coral / sage / teal / mustard

export default function QuizRace({
  question, players = [], view = 'student', onAnswer, config = {},
  questionIndex = 0, totalQuestions = 1, lastResult = null,
}) {
  const timer = config.timer_seconds || 20;
  const [remaining, setRemaining] = useState(timer);
  const [selected, setSelected] = useState(null);
  const [muted, setMutedState] = useState(false);
  const [streak, setStreak] = useState(0);
  const [showLeaderboard, setShowLeaderboard] = useState(false);
  const prevIndexRef = useRef(questionIndex);
  const tickRef = useRef(null);

  // Reset per question + play whoosh
  useEffect(() => {
    setSelected(null);
    setRemaining(timer);
    if (question && prevIndexRef.current !== questionIndex) {
      play('whoosh');
      prevIndexRef.current = questionIndex;
    }
  }, [question?.question_text, questionIndex, timer]);

  // Countdown tick
  useEffect(() => {
    if (!timer || remaining <= 0 || selected) return;
    tickRef.current = setTimeout(() => {
      setRemaining(r => {
        const next = r - 1;
        if (next > 0 && next <= 5) play('tickUrgent');
        else if (next > 0) play('tick');
        return next;
      });
    }, 1000);
    return () => clearTimeout(tickRef.current);
  }, [remaining, timer, selected]);

  // Play result sound + confetti + streak tracking
  const resultSeen = useRef(null);
  useEffect(() => {
    if (lastResult && resultSeen.current !== questionIndex) {
      resultSeen.current = questionIndex;
      if (lastResult.correct) {
        play('correct');
        correctAnswer({ x: 0.5, y: 0.55 });
        setStreak(s => s + 1);
      } else {
        play('incorrect');
        setStreak(0);
      }
    }
  }, [lastResult, questionIndex]);

  // Teacher-only: between-question leaderboard reveal when question advances
  const prevQuestionIdRef = useRef(questionIndex);
  useEffect(() => {
    if (view !== 'teacher') return;
    if (questionIndex > prevQuestionIdRef.current && players.length > 0) {
      setShowLeaderboard(true);
      play('drumroll');
      const t = setTimeout(() => setShowLeaderboard(false), 2200);
      prevQuestionIdRef.current = questionIndex;
      return () => clearTimeout(t);
    }
    prevQuestionIdRef.current = questionIndex;
  }, [questionIndex, view, players.length]);

  function toggleMute() {
    const v = !muted;
    setMuted(v);
    setMutedState(v);
  }

  if (!question) {
    return (
      <div className="rounded-card p-10 text-center"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <p className="font-serif text-[20px]" style={{ color: 'var(--text-mid)' }}>
          Waiting for the next question…
        </p>
      </div>
    );
  }

  const timerPct = timer > 0 ? Math.max(0, Math.min(1, remaining / timer)) : 0;
  const urgentTimer = remaining <= 5 && remaining > 0;

  return (
    <div className="max-w-3xl mx-auto relative">
      {/* Top meta bar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <motion.span
            key={`q-${questionIndex}`}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="text-[11px] font-bold uppercase tracking-[2px] px-3 py-1 rounded-full"
            style={{ color: 'white', background: 'var(--coral)' }}>
            Question {questionIndex + 1} of {totalQuestions}
          </motion.span>
          <AnimatePresence>
            {view === 'student' && streak >= 2 && (
              <motion.span
                key={`streak-${streak}`}
                initial={{ opacity: 0, scale: 0.6, y: -4 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.6 }}
                transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-[1px] px-3 py-1 rounded-full"
                style={{ color: 'white', background: 'linear-gradient(135deg, #F97316, #DC2626)', boxShadow: '0 0 12px rgba(249,115,22,0.55)' }}>
                <Flame className="w-3 h-3" /> {streak} in a row
              </motion.span>
            )}
          </AnimatePresence>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-[13px] font-bold" style={{ color: 'var(--text-mid)' }}>
            <Users className="w-4 h-4" /> {players.length}
          </span>
          <button onClick={toggleMute}
            className="p-1.5 rounded-full"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer', color: 'var(--text-mid)' }}>
            {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
          {timer > 0 && <CircularTimer pct={timerPct} urgent={urgentTimer} seconds={remaining} />}
        </div>
      </div>

      {/* Question card */}
      <AnimatePresence mode="wait">
        <motion.div
          key={`qcard-${questionIndex}`}
          initial={{ opacity: 0, y: 30, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.98 }}
          transition={{ type: 'spring', stiffness: 260, damping: 22 }}
          className="rounded-card p-8 mb-5 text-center"
          style={{
            background: 'var(--warm-card)',
            border: '1px solid var(--border)',
            boxShadow: '0 10px 32px rgba(60,40,20,0.1)',
          }}>
          <h2 className="font-serif text-[28px] leading-tight" style={{ color: 'var(--text-dark)' }}>
            {question.question_text}
          </h2>
        </motion.div>
      </AnimatePresence>

      {/* Student: answer tiles */}
      {view === 'student' && (
        <div className="grid grid-cols-2 gap-3">
          {(question.options || []).map((opt, i) => (
            <AnswerTile key={`${questionIndex}-${i}`} index={i} opt={opt}
              color={TILE_COLORS[i]}
              selected={selected === opt}
              lastResult={lastResult}
              disabled={!!selected || remaining <= 0}
              onClick={() => { setSelected(opt); onAnswer?.(opt); }} />
          ))}
        </div>
      )}

      {/* Teacher: show answer + player grid */}
      {/* Between-question leaderboard reveal — teacher only, after teacher advances */}
      <AnimatePresence>
        {view === 'teacher' && showLeaderboard && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 280, damping: 22 }}
            className="fixed inset-0 z-40 flex items-center justify-center p-6"
            style={{ background: 'rgba(60,40,20,0.55)', backdropFilter: 'blur(6px)' }}>
            <div className="rounded-card w-full max-w-md p-6"
              style={{ background: 'var(--warm-card)', border: '2px solid var(--coral)', boxShadow: '0 12px 40px rgba(60,40,20,0.3)' }}>
              <h3 className="font-serif text-[22px] text-center mb-4" style={{ color: 'var(--text-dark)' }}>
                Leaderboard
              </h3>
              <div className="space-y-2">
                {[...players].sort((a,b) => (b.score||0) - (a.score||0)).slice(0, 5).map((p, i) => (
                  <motion.div key={p.player_id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.12 }}
                    className="flex items-center justify-between p-2.5 rounded-xl"
                    style={{
                      background: i === 0 ? 'rgba(233,180,76,0.15)' : 'var(--cream)',
                      border: `1px solid ${i === 0 ? 'var(--mustard, #E9B44C)' : 'var(--border)'}`,
                    }}>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[14px] w-6 text-center" style={{ color: i === 0 ? '#B48838' : 'var(--text-mid)' }}>
                        {i === 0 ? '🏆' : `#${i + 1}`}
                      </span>
                      <span className="text-[20px]">{p.avatar || '🐻'}</span>
                      <span className="font-serif text-[14px]" style={{ color: 'var(--text-dark)' }}>{p.name}</span>
                    </div>
                    <span className="font-bold text-[14px]" style={{ color: 'var(--coral)' }}>{p.score || 0}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {view === 'teacher' && (
        <div>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}
            className="rounded-card p-4 mb-4 text-center"
            style={{ background: 'rgba(107,160,138,0.08)', border: '1px solid var(--sage)' }}>
            <p className="text-[11px] uppercase tracking-wider font-bold" style={{ color: 'var(--sage)' }}>
              Correct answer
            </p>
            <p className="text-[18px] font-bold font-serif mt-1" style={{ color: 'var(--text-dark)' }}>
              {question.answer}
            </p>
          </motion.div>
          <motion.div
            className="grid gap-2"
            style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))' }}
            initial="hidden" animate="show"
            variants={{ hidden: {}, show: { transition: { staggerChildren: 0.04 } } }}>
            {players.map((p) => (
              <motion.div key={p.player_id}
                variants={{ hidden: { opacity: 0, scale: 0.9 }, show: { opacity: 1, scale: 1 } }}
                className="rounded-xl p-2 text-center"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                <div className="text-[22px]">{p.avatar || '🐻'}</div>
                <div className="text-[11px] font-bold truncate" style={{ color: 'var(--text-dark)' }}>{p.name}</div>
                <motion.div key={p.score}
                  initial={{ scale: 1.4, color: 'var(--coral)' }}
                  animate={{ scale: 1, color: 'var(--coral)' }}
                  transition={{ duration: 0.25 }}
                  className="text-[12px] font-bold">
                  {p.score || 0}
                </motion.div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      )}

      {/* Student result banner */}
      <AnimatePresence>
        {view === 'student' && lastResult && (
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ type: 'spring', stiffness: 400, damping: 24 }}
            className="mt-5 rounded-card p-4 text-center"
            style={{
              background: lastResult.correct ? 'rgba(22,163,74,0.12)' : 'rgba(239,68,68,0.1)',
              border: `2px solid ${lastResult.correct ? '#16A34A' : '#EF4444'}`,
            }}>
            {lastResult.correct ? (
              <span className="font-bold font-serif text-[22px] flex items-center justify-center gap-2" style={{ color: '#16A34A' }}>
                <Trophy className="w-6 h-6" />
                <motion.span
                  initial={{ scale: 0 }} animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 15, delay: 0.1 }}>
                  +{lastResult.points} points
                </motion.span>
              </span>
            ) : (
              <span className="font-bold text-[16px]" style={{ color: '#B91C1C' }}>
                Not quite. Correct answer: <strong>{lastResult.correct_answer}</strong>
              </span>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AnswerTile({ index, opt, color, selected, lastResult, disabled, onClick }) {
  const isCorrect = lastResult && lastResult.correct_answer === opt;
  const isWrongSelected = lastResult && selected && !lastResult.correct;
  const revealed = !!lastResult;

  const tileMotion = revealed && isWrongSelected ? {
    animate: { x: [0, -8, 8, -6, 6, -3, 0] },
    transition: { duration: 0.4 },
  } : revealed && isCorrect ? {
    animate: { scale: [1, 1.08, 1] },
    transition: { duration: 0.5 },
  } : {};

  return (
    <motion.button
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0, ...tileMotion.animate }}
      transition={{ delay: 0.15 + index * 0.08, duration: 0.4, ...tileMotion.transition }}
      whileTap={{ scale: disabled ? 1 : 0.96 }}
      whileHover={{ scale: disabled ? 1 : 1.02 }}
      disabled={disabled}
      onClick={onClick}
      className="rounded-card p-5 text-left font-bold text-[16px] relative overflow-hidden"
      style={{
        background: revealed
          ? (isCorrect ? 'linear-gradient(135deg, #16A34A, #22C55E)' : isWrongSelected ? 'linear-gradient(135deg, #EF4444, #F87171)' : 'var(--cream)')
          : selected ? `${color}E6` : color,
        color: revealed && !isCorrect && !isWrongSelected ? 'var(--text-mid)' : 'white',
        border: selected && !revealed ? '3px solid white' : 'none',
        boxShadow: revealed
          ? (isCorrect || isWrongSelected ? '0 8px 28px rgba(60,40,20,0.25)' : '0 2px 6px rgba(60,40,20,0.08)')
          : '0 4px 14px rgba(60,40,20,0.15)',
        opacity: revealed && !isCorrect && !isWrongSelected ? 0.5 : 1,
        cursor: disabled ? 'default' : 'pointer',
      }}>
      <div className="flex items-center gap-3">
        <span className="inline-flex items-center justify-center w-9 h-9 rounded-full text-[15px] flex-shrink-0"
          style={{
            background: revealed ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.25)',
            color: revealed && !isCorrect && !isWrongSelected ? 'var(--text-mid)' : 'white',
            fontWeight: 900,
          }}>
          {String.fromCharCode(65 + index)}
        </span>
        <span className="flex-1 leading-tight">{opt}</span>
        {revealed && isCorrect && <CheckCircle className="w-6 h-6 flex-shrink-0" />}
        {revealed && isWrongSelected && <XCircle className="w-6 h-6 flex-shrink-0" />}
      </div>
    </motion.button>
  );
}

function CircularTimer({ pct, urgent, seconds }) {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct);
  const color = urgent ? '#EF4444' : pct > 0.33 ? 'var(--sage)' : 'var(--coral)';

  return (
    <motion.div
      animate={urgent ? { scale: [1, 1.12, 1] } : { scale: 1 }}
      transition={{ duration: 0.5, repeat: urgent ? Infinity : 0 }}
      className="relative"
      style={{ width: 44, height: 44 }}>
      <svg width="44" height="44" viewBox="0 0 44 44" className="-rotate-90">
        <circle cx="22" cy="22" r={radius} stroke="var(--cream)" strokeWidth="4" fill="none" />
        <motion.circle cx="22" cy="22" r={radius}
          stroke={color} strokeWidth="4" fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: 'linear' }} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[13px] font-bold"
        style={{ color }}>
        {seconds}
      </span>
    </motion.div>
  );
}
