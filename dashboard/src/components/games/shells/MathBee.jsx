'use client';
import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bug, Zap, Crown, Delete, CornerDownLeft } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer, winnerCelebration } from '@/lib/confetti';
import { ArcadeChip } from '@/components/games/CabinetStage';

/**
 * Math Bee — arcade-cabinet edition (v1 April 2026). NEW SHELL.
 *
 * Neon lime #B6FF39 accent from registry. Honeycomb-hex grid motif on dark
 * stage. Rapid-fire math fluency — equation flashes, student types answer on
 * an on-screen numpad (0–9, backspace, enter).
 *
 * Renders inside CabinetStage. Interior content only — no full-page bg.
 *
 * Two modes (from config.mode):
 *   - "blitz"  (default): race the clock. Live APM counter. Score = correct count.
 *   - "ladder": climb bee tiers (Worker→Drone→Guard→Nurse→Queen) by streak.
 *     Miss resets to previous tier (not to bottom).
 *
 * Streak tiers (both modes):
 *   3 → Buzzing   ×1.5   🐝
 *   6 → Swarming  ×2     🐝🐝
 *  10 → Royal Jelly ×3   👑
 *
 * Server contract: onAnswer(answer_text) fires on Enter with the typed value.
 * Backend scores it — shell gets lastResult { correct, correct_answer }.
 *
 * Questions come from allQuestions / question via normal game WebSocket.
 * The shell only needs { question_text, answer } (numeric answer).
 */

// Streak tier definitions
const STREAK_TIERS = [
  { min: 0,  label: 'READY',       mult: 1,   icon: null },
  { min: 3,  label: 'BUZZING',     mult: 1.5, icon: '🐝' },
  { min: 6,  label: 'SWARMING',    mult: 2,   icon: '🐝🐝' },
  { min: 10, label: 'ROYAL JELLY', mult: 3,   icon: '👑' },
];

function getStreakTier(streak) {
  for (let i = STREAK_TIERS.length - 1; i >= 0; i--) {
    if (streak >= STREAK_TIERS[i].min) return STREAK_TIERS[i];
  }
  return STREAK_TIERS[0];
}

// Ladder tiers for ladder mode
const LADDER_TIERS = [
  { name: 'WORKER',  emoji: '🐝', min: 0 },
  { name: 'DRONE',   emoji: '🐝', min: 5 },
  { name: 'GUARD',   emoji: '🛡', min: 10 },
  { name: 'NURSE',   emoji: '💉', min: 18 },
  { name: 'QUEEN',   emoji: '👑', min: 25 },
];
function getLadderTier(correct) {
  for (let i = LADDER_TIERS.length - 1; i >= 0; i--) {
    if (correct >= LADDER_TIERS[i].min) return { ...LADDER_TIERS[i], index: i };
  }
  return { ...LADDER_TIERS[0], index: 0 };
}

export default function MathBee({
  allQuestions = [], question, players = [], view = 'student',
  onAnswer, config = {},
  questionIndex = 0, totalQuestions = 30, lastResult = null, playerId = null,
}) {
  const mode = config.mode || 'blitz';

  const [input, setInput] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [streak, setStreak] = useState(0);
  const [bestStreak, setBestStreak] = useState(0);
  const [score, setScore] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [wrongCount, setWrongCount] = useState(0);
  const [showResult, setShowResult] = useState(null); // 'correct' | 'wrong'
  const [correctAnswerText, setCorrectAnswerText] = useState('');
  const [startedAt] = useState(() => Date.now());
  const [gameOver, setGameOver] = useState(false);

  // APM tracking (answers per minute)
  const [apm, setApm] = useState(0);
  const apmInterval = useRef(null);

  useEffect(() => {
    if (mode !== 'blitz' || view !== 'student') return;
    apmInterval.current = setInterval(() => {
      const elapsed = (Date.now() - startedAt) / 60000; // minutes
      if (elapsed > 0) setApm(Math.round(correctCount / elapsed));
    }, 1000);
    return () => clearInterval(apmInterval.current);
  }, [mode, view, correctCount, startedAt]);

  // Reset input on new question
  useEffect(() => {
    setInput('');
    setSubmitted(false);
    setShowResult(null);
    setCorrectAnswerText('');
  }, [question?.question_text]);

  // Handle result from backend
  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) {
      play('correct');
      correctAnswer({ x: 0.5, y: 0.45 });
      setShowResult('correct');
      setStreak(s => s + 1);
      setBestStreak(b => Math.max(b, streak + 1));
      setCorrectCount(c => c + 1);
      const tier = getStreakTier(streak + 1);
      setScore(s => s + Math.round(100 * tier.mult));
    } else {
      play('incorrect');
      setShowResult('wrong');
      setCorrectAnswerText(lastResult.correct_answer || question?.answer || '?');
      setStreak(0);
      setWrongCount(w => w + 1);
    }
    // Clear result flash after delay
    const t = setTimeout(() => setShowResult(null), 1200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastResult]);

  // Game over detection
  useEffect(() => {
    if (questionIndex >= totalQuestions - 1 && lastResult && !gameOver) {
      setTimeout(() => {
        setGameOver(true);
        play('fanfare');
        winnerCelebration();
      }, 1400);
    }
  }, [questionIndex, totalQuestions, lastResult, gameOver]);

  // Numpad handlers
  const appendDigit = useCallback((d) => {
    if (submitted || showResult) return;
    setInput(prev => {
      if (d === '-' && prev.length === 0) return '-';
      if (d === '.' && prev.includes('.')) return prev;
      if (prev.length >= 10) return prev;
      return prev + d;
    });
    play('tick');
  }, [submitted, showResult]);

  const backspace = useCallback(() => {
    if (submitted || showResult) return;
    setInput(prev => prev.slice(0, -1));
  }, [submitted, showResult]);

  const submitAnswer = useCallback(() => {
    if (submitted || !input || showResult) return;
    setSubmitted(true);
    play('whoosh');
    onAnswer?.(input);
  }, [submitted, input, showResult, onAnswer]);

  // Keyboard support
  useEffect(() => {
    function handleKey(e) {
      if (view !== 'student' || gameOver) return;
      if (e.key >= '0' && e.key <= '9') appendDigit(e.key);
      else if (e.key === '.') appendDigit('.');
      else if (e.key === '-') appendDigit('-');
      else if (e.key === 'Backspace') backspace();
      else if (e.key === 'Enter') submitAnswer();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [view, gameOver, appendDigit, backspace, submitAnswer]);

  const tier = getStreakTier(streak);
  const ladderTier = getLadderTier(correctCount);

  // HUD
  const hudLeft = (
    <>
      <ArcadeChip>Q {questionIndex + 1}/{totalQuestions}</ArcadeChip>
      {mode === 'blitz' && (
        <ArcadeChip variant="ghost">APM {apm}</ArcadeChip>
      )}
      {mode === 'ladder' && (
        <ArcadeChip>{ladderTier.emoji} {ladderTier.name}</ArcadeChip>
      )}
    </>
  );
  const hudRight = (
    <>
      <ArcadeChip variant={streak >= 3 ? 'solid' : 'ghost'}>
        {tier.icon || '🐝'} ×{tier.mult}
      </ArcadeChip>
      <ArcadeChip variant="ghost">✓{correctCount} ✗{wrongCount}</ArcadeChip>
      <ArcadeChip>SCORE {score}</ArcadeChip>
    </>
  );

  // ── GAME OVER ──
  if (gameOver) {
    const elapsed = Math.round((Date.now() - startedAt) / 1000);
    const finalApm = elapsed > 0 ? Math.round((correctCount / elapsed) * 60) : 0;
    return (
      <div style={{ padding: '4px 0 24px', color: 'var(--arcade-ink, #F7F7FF)' }}>
        <StageHudBand left={hudLeft} right={hudRight} />
        <motion.div
          initial={{ opacity: 0, scale: 0.85, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 220, damping: 18 }}
          style={{
            maxWidth: 620, margin: '40px auto',
            padding: '36px 28px', textAlign: 'center',
            background: 'linear-gradient(180deg, rgba(182,255,57,0.15), rgba(10,10,24,0.85))',
            border: '2px solid var(--arcade-accent, #B6FF39)',
            borderRadius: 18,
            boxShadow: '0 0 40px color-mix(in srgb, var(--arcade-accent, #B6FF39) 35%, transparent)',
          }}
        >
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 12,
            letterSpacing: 2.5, color: 'var(--arcade-accent, #B6FF39)', marginBottom: 12,
          }}>
            {correctCount >= totalQuestions * 0.9 ? '★ BEE-UTIFUL ★' : '★ TIME\'S UP ★'}
          </div>
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 26,
            letterSpacing: 2, color: '#B6FF39', marginBottom: 16,
            textShadow: '0 0 18px rgba(182,255,57,0.6)',
          }}>
            {score} PTS
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
            <WinStat label="CORRECT" value={`${correctCount}/${totalQuestions}`} />
            <WinStat label="BEST STREAK" value={bestStreak} />
            {mode === 'blitz' && <WinStat label="APM" value={finalApm} />}
            {mode === 'ladder' && <WinStat label="TIER" value={ladderTier.name} />}
            <WinStat label="TIME" value={`${elapsed}s`} />
          </div>
        </motion.div>
      </div>
    );
  }

  // ── STUDENT VIEW ──
  if (view === 'student') {
    return (
      <div style={{ padding: '4px 0 24px', color: 'var(--arcade-ink, #F7F7FF)' }}>
        <StageHudBand left={hudLeft} right={hudRight} />

        {/* Equation display */}
        <div style={{
          maxWidth: 700, margin: '0 auto 16px',
          padding: '28px 24px',
          borderRadius: 18,
          background: `
            radial-gradient(circle at 50% 0%, rgba(182,255,57,0.12), transparent 55%),
            linear-gradient(180deg, #0F0F24, #0A0A1A)`,
          border: '2px solid var(--arcade-accent, #B6FF39)',
          boxShadow: `
            0 0 24px color-mix(in srgb, var(--arcade-accent, #B6FF39) 25%, transparent),
            0 12px 40px rgba(0,0,0,0.55)`,
          textAlign: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}>
          {/* Honeycomb bg accent */}
          <div style={{
            position: 'absolute', inset: 0, opacity: 0.06,
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='100'%3E%3Cpath d='M28 66L0 50L0 16L28 0L56 16L56 50L28 66L28 100' fill='none' stroke='%23B6FF39' stroke-width='1'/%3E%3C/svg%3E")`,
            backgroundSize: '56px 100px',
            pointerEvents: 'none',
          }} />

          {/* Streak tier banner */}
          <AnimatePresence>
            {streak >= 3 && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 10, letterSpacing: 2.5,
                  color: '#B6FF39', marginBottom: 10,
                }}
              >
                {tier.icon} {tier.label} ×{tier.mult} {tier.icon}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Question text */}
          <AnimatePresence mode="wait">
            <motion.div
              key={question?.question_text || questionIndex}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
              style={{
                fontFamily: 'Space Grotesk, sans-serif',
                fontWeight: 700,
                fontSize: 'clamp(28px, 5vw, 44px)',
                lineHeight: 1.2,
                color: '#E8FFE1',
                textShadow: '0 0 12px rgba(182,255,57,0.25)',
                padding: '4px 0 12px',
                position: 'relative', zIndex: 1,
              }}
            >
              {question?.question_text || '...'}
            </motion.div>
          </AnimatePresence>

          {/* Answer input display */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            position: 'relative', zIndex: 1,
          }}>
            <motion.div
              animate={
                showResult === 'correct' ? { scale: [1, 1.08, 1], borderColor: '#16D474' }
                  : showResult === 'wrong' ? { x: [-3, 3, -3, 3, 0], borderColor: '#FF3864' }
                    : { borderColor: submitted ? 'rgba(182,255,57,0.4)' : 'rgba(182,255,57,0.6)' }
              }
              transition={{ duration: 0.4 }}
              style={{
                minWidth: 160, maxWidth: 280,
                padding: '14px 20px',
                borderRadius: 14,
                background: 'rgba(10,10,24,0.75)',
                border: '2px solid rgba(182,255,57,0.6)',
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 24, letterSpacing: 3,
                color: showResult === 'correct' ? '#16D474'
                  : showResult === 'wrong' ? '#FF3864'
                    : 'var(--arcade-ink, #F7F7FF)',
                textAlign: 'center',
                boxShadow: showResult === 'correct'
                  ? '0 0 20px rgba(22,212,116,0.4)'
                  : showResult === 'wrong'
                    ? '0 0 20px rgba(255,56,100,0.4)'
                    : '0 0 12px rgba(182,255,57,0.15)',
              }}
            >
              {input || (showResult === 'wrong' ? correctAnswerText : '—')}
              {!submitted && !showResult && (
                <span style={{
                  display: 'inline-block', width: 2, height: 24,
                  background: 'var(--arcade-accent, #B6FF39)',
                  marginLeft: 4, verticalAlign: 'middle',
                  animation: 'blink 0.8s step-end infinite',
                }} />
              )}
            </motion.div>
          </div>

          {/* Result feedback text */}
          <AnimatePresence>
            {showResult === 'wrong' && correctAnswerText && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{
                  marginTop: 10,
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 10, letterSpacing: 1.5,
                  color: '#FF3864',
                  position: 'relative', zIndex: 1,
                }}
              >
                ANSWER: {correctAnswerText}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* On-screen numpad */}
        <Numpad
          onDigit={appendDigit}
          onBackspace={backspace}
          onEnter={submitAnswer}
          disabled={submitted || !!showResult}
        />

        {/* Streak preview */}
        {streak >= 1 && streak < 10 && (
          <div style={{
            textAlign: 'center', marginTop: 12,
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 9, letterSpacing: 2,
            color: streak >= 3 ? '#B6FF39' : 'rgba(247,247,255,0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
            <Zap style={{ width: 12, height: 12 }} />
            STREAK {streak} — NEXT TIER AT {nextTierAt(streak)}
          </div>
        )}
      </div>
    );
  }

  // ── TEACHER VIEW ──
  return (
    <div style={{ padding: '4px 0 24px', color: 'var(--arcade-ink, #F7F7FF)' }}>
      <StageHudBand left={hudLeft} right={hudRight} />
      <TeacherBoard
        question={question}
        questionIndex={questionIndex}
        totalQuestions={totalQuestions}
        players={players}
        mode={mode}
      />
    </div>
  );
}

// ============================================================
//                     Numpad component
// ============================================================

const NUMPAD_KEYS = [
  ['7', '8', '9'],
  ['4', '5', '6'],
  ['1', '2', '3'],
  ['-', '0', '.'],
];

function Numpad({ onDigit, onBackspace, onEnter, disabled }) {
  return (
    <div style={{
      maxWidth: 360, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      {NUMPAD_KEYS.map((row, ri) => (
        <div key={ri} style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
          {row.map(k => (
            <motion.button
              key={k}
              whileTap={{ scale: 0.93 }}
              disabled={disabled}
              onClick={() => onDigit(k)}
              style={{
                width: 72, height: 60,
                borderRadius: 12,
                border: 'none',
                background: 'linear-gradient(180deg, #1D1636, #120C26)',
                color: 'var(--arcade-ink, #F7F7FF)',
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 18,
                cursor: disabled ? 'default' : 'pointer',
                boxShadow: `
                  inset 0 1px 0 rgba(255,255,255,0.08),
                  0 4px 0 #0A0818,
                  0 6px 14px rgba(0,0,0,0.5)`,
                opacity: disabled ? 0.4 : 1,
                transition: 'opacity 0.15s',
              }}
            >
              {k}
            </motion.button>
          ))}
        </div>
      ))}
      {/* Bottom row: backspace + ENTER */}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
        <motion.button
          whileTap={{ scale: 0.93 }}
          disabled={disabled}
          onClick={onBackspace}
          style={{
            width: 110, height: 56,
            borderRadius: 12, border: 'none',
            background: 'linear-gradient(180deg, #2A1220, #1A0818)',
            color: '#FF3864',
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 11, letterSpacing: 1,
            cursor: disabled ? 'default' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 0 #0A0818, 0 6px 14px rgba(0,0,0,0.5)',
            opacity: disabled ? 0.4 : 1,
          }}
        >
          <Delete style={{ width: 14, height: 14 }} /> DEL
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.93 }}
          disabled={disabled}
          onClick={onEnter}
          style={{
            width: 148, height: 56,
            borderRadius: 12, border: 'none',
            background: 'linear-gradient(180deg, #2A4A10, #1A3008)',
            color: '#B6FF39',
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 13, letterSpacing: 1.5,
            cursor: disabled ? 'default' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            boxShadow: `
              inset 0 1px 0 rgba(255,255,255,0.08),
              0 0 14px rgba(182,255,57,0.2),
              0 4px 0 #0A2008,
              0 6px 14px rgba(0,0,0,0.5)`,
            opacity: disabled ? 0.4 : 1,
          }}
        >
          <CornerDownLeft style={{ width: 14, height: 14 }} /> ENTER
        </motion.button>
      </div>
    </div>
  );
}

// ============================================================
//                 TeacherBoard — live scoreboard
// ============================================================

function TeacherBoard({ question, questionIndex, totalQuestions, players, mode }) {
  const rows = useMemo(() => {
    return (players || []).map(p => {
      const correct = p.answers_correct ?? 0;
      const tier = getStreakTier(p.current_streak ?? 0);
      const ladderTier = getLadderTier(correct);
      return {
        id: p.player_id || p.id,
        name: p.name || p.display_name || 'Player',
        score: p.score || 0,
        correct,
        streak: p.current_streak ?? 0,
        tier, ladderTier,
      };
    }).sort((a, b) => b.score - a.score);
  }, [players]);

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* Current question display */}
      <div style={{
        padding: '20px 24px', marginBottom: 16,
        borderRadius: 14,
        background: `
          radial-gradient(circle at 50% 0%, rgba(182,255,57,0.1), transparent 55%),
          linear-gradient(180deg, #0F0F24, #0A0A1A)`,
        border: '2px solid var(--arcade-accent, #B6FF39)',
        boxShadow: '0 0 24px rgba(182,255,57,0.2)',
        textAlign: 'center',
      }}>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2, color: 'var(--arcade-ink-dim, #B6B7D8)',
          marginBottom: 8,
        }}>
          QUESTION {questionIndex + 1} OF {totalQuestions}
        </div>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 28, fontWeight: 700,
          color: '#E8FFE1',
          textShadow: '0 0 10px rgba(182,255,57,0.2)',
        }}>
          {question?.question_text || 'Waiting...'}
        </div>
        {question?.answer && (
          <div style={{
            marginTop: 8,
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 14, color: '#B6FF39',
          }}>
            = {question.answer}
          </div>
        )}
      </div>

      {/* Player leaderboard */}
      <div style={{
        padding: '16px 18px',
        borderRadius: 14,
        background: 'linear-gradient(180deg, rgba(10,10,24,0.75), rgba(10,10,24,0.55))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2,
          color: 'var(--arcade-accent, #B6FF39)',
          marginBottom: 12,
        }}>
          HIVE · {rows.length} PLAYER{rows.length === 1 ? '' : 'S'}
        </div>

        {rows.length === 0 ? (
          <div style={{ fontSize: 13, color: 'rgba(247,247,255,0.55)' }}>
            Waiting for students to buzz in…
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rows.map((r, idx) => (
              <div
                key={r.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '10px 14px',
                  borderRadius: 10,
                  background: idx === 0
                    ? 'linear-gradient(90deg, rgba(182,255,57,0.12), rgba(10,10,24,0.7))'
                    : 'rgba(10,10,24,0.6)',
                  border: `1px solid ${idx === 0 ? 'rgba(182,255,57,0.35)' : 'rgba(255,255,255,0.06)'}`,
                }}
              >
                {/* Rank */}
                <div style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 14, color: idx === 0 ? '#B6FF39' : 'rgba(247,247,255,0.45)',
                  minWidth: 30,
                }}>
                  {idx + 1}.
                </div>
                {/* Name + tier */}
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontFamily: 'Space Grotesk, sans-serif',
                    fontSize: 14, fontWeight: 700,
                    color: idx === 0 ? '#B6FF39' : 'rgba(247,247,255,0.85)',
                  }}>
                    {r.name}
                  </div>
                  <div style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 8, letterSpacing: 1.5,
                    color: 'rgba(247,247,255,0.5)', marginTop: 2,
                  }}>
                    {mode === 'ladder' ? `${r.ladderTier.emoji} ${r.ladderTier.name}` : `${r.tier.icon || '🐝'} ${r.tier.label}`}
                    {r.streak >= 3 && ` · STREAK ${r.streak}`}
                  </div>
                </div>
                {/* Score */}
                <div style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 14, color: idx === 0 ? '#B6FF39' : 'var(--arcade-ink, #F7F7FF)',
                }}>
                  {r.score}
                </div>
                {/* Correct count */}
                <div style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 9, color: 'rgba(247,247,255,0.5)',
                  minWidth: 40, textAlign: 'right',
                }}>
                  ✓{r.correct}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
//                     StageHudBand
// ============================================================

function StageHudBand({ left, right }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 14px', borderRadius: 12,
      background: 'linear-gradient(180deg, rgba(10,10,24,0.85), rgba(10,10,24,0.6))',
      border: '1px solid rgba(255,255,255,0.08)',
      marginBottom: 14, gap: 12, flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>{left}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>{right}</div>
    </div>
  );
}

// ============================================================
//                     WinStat helper
// ============================================================

function WinStat({ label, value }) {
  return (
    <div style={{
      padding: '8px 14px', borderRadius: 10,
      background: 'rgba(10,10,24,0.6)',
      border: '1px solid rgba(255,255,255,0.1)',
      textAlign: 'center', minWidth: 80,
    }}>
      <div style={{
        fontFamily: "'Press Start 2P', monospace",
        fontSize: 8, letterSpacing: 1.5, color: 'rgba(247,247,255,0.5)', marginBottom: 4,
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: "'Press Start 2P', monospace", fontSize: 14, color: '#B6FF39',
      }}>
        {value}
      </div>
    </div>
  );
}

// ============================================================
//                     Helpers
// ============================================================

function nextTierAt(streak) {
  for (const t of STREAK_TIERS) {
    if (t.min > streak) return t.min;
  }
  return '—';
}
