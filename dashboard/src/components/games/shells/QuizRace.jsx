'use client';
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, Users, Flame } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer } from '@/lib/confetti';
import { ArcadeChip, ArcadeLedTimer } from '@/components/games/CabinetStage';
import Racetrack from '@/components/games/Racetrack';

/**
 * Quiz Race — Kahoot-style MC, arcade-cabinet edition.
 *
 * v2 (April 2026): fully adopts the shared in-cabinet chrome (dark neon,
 * Press Start 2P marquee, LED segment timer, arcade-button tiles). The
 * outer frame (marquee + scanlines + accent color) is provided by
 * CabinetStage which wraps this shell in /play and /join.
 *
 * This file now owns the interior gameplay only:
 *   - Question "screen" (dark panel with accent border + inner glow)
 *   - Four arcade-button answer tiles (coral / teal / mustard / sage)
 *   - Streak banner with escalating glow
 *   - Result splash on correct/wrong
 *   - Teacher leaderboard reveal between questions
 *
 * Shell contract (unchanged):
 *   question, players, view, onAnswer, config,
 *   questionIndex, totalQuestions, lastResult
 */

const TILE_COLORS = ['#FF3864', '#3A86FF', '#FFBE0B', '#2EC4B6']; // coral / teal / mustard / sage

export default function QuizRace({
  question, players = [], view = 'student', onAnswer, config = {},
  questionIndex = 0, totalQuestions = 1, lastResult = null,
  playerId = null,
}) {
  // Student view needs at least its own player row on the track. When the
  // student joins, /join passes playerId; we synthesize a lightweight "self"
  // entry if the players array is empty (teacher hasn't broadcast it yet).
  const trackPlayers = (players && players.length > 0)
    ? players
    : (view === 'student' && playerId
        ? [{ player_id: playerId, name: 'YOU', score: 0 }]
        : []);
  const timer = config.timer_seconds || 20;
  const [remaining, setRemaining] = useState(timer);
  const [selected, setSelected] = useState(null);
  const [streak, setStreak] = useState(0);
  const [showLeaderboard, setShowLeaderboard] = useState(false);
  const [splash, setSplash] = useState(null); // { kind: 'win'|'lose', points, correctLetter }
  const prevIndexRef = useRef(questionIndex);
  const tickRef = useRef(null);

  // Reset per question + play whoosh
  useEffect(() => {
    setSelected(null);
    setRemaining(timer);
    setSplash(null);
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

  // Play result sound + confetti + streak tracking + splash
  const resultSeen = useRef(null);
  useEffect(() => {
    if (lastResult && resultSeen.current !== questionIndex) {
      resultSeen.current = questionIndex;
      const correctLetter = findLetter(question?.options, lastResult.correct_answer);
      if (lastResult.correct) {
        play('correct');
        correctAnswer({ x: 0.5, y: 0.55 });
        setStreak(s => s + 1);
        setSplash({ kind: 'win', points: lastResult.points });
      } else {
        play('incorrect');
        setStreak(0);
        setSplash({ kind: 'lose', correctLetter });
      }
      const t = setTimeout(() => setSplash(null), 1200);
      return () => clearTimeout(t);
    }
  }, [lastResult, questionIndex, question?.options]);

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

  if (!question) {
    return (
      <div className="arcade-screen" style={{ textAlign: 'center' }}>
        <p className="arcade-screen__q" style={{ opacity: 0.8 }}>
          Waiting for the next question…
        </p>
      </div>
    );
  }

  const timerPct = timer > 0 ? Math.max(0, Math.min(1, remaining / timer)) : 0;

  return (
    <div style={{ position: 'relative' }}>
      {/* Interior HUD band (marquee/bulbs/mute live in CabinetStage above this). */}
      <div className="arcade-hud" style={{ marginTop: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <motion.div
            key={`q-${questionIndex}`}
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ArcadeChip>Q {questionIndex + 1} / {totalQuestions}</ArcadeChip>
          </motion.div>
          <AnimatePresence>
            {view === 'student' && streak >= 2 && (
              <motion.span
                key={`streak-${streak}`}
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.6 }}
                transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                className="arcade-hud-chip"
                style={{
                  background: streak >= 5
                    ? 'linear-gradient(135deg, #FF006E, #FF3864)'
                    : 'linear-gradient(135deg, #FFBE0B, #FF8A00)',
                  color: '#0A0A18',
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                }}>
                <Flame style={{ width: 11, height: 11 }} /> {streak}× STREAK
              </motion.span>
            )}
          </AnimatePresence>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            color: 'var(--arcade-ink-dim)', fontSize: 12, fontWeight: 600,
          }}>
            <Users style={{ width: 14, height: 14 }} /> {players.length}
          </span>
          {timer > 0 && <ArcadeLedTimer pct={timerPct} seconds={remaining} segments={20} />}
        </div>
      </div>

      {/* Racetrack — big on teacher view, compact strip on student view.
          Path 1: progress is derived client-side from each player's score
          (Racetrack.jsx handles the math). Path 2 would swap to server
          events. */}
      {trackPlayers.length > 0 && (
        <Racetrack
          players={trackPlayers}
          totalQuestions={totalQuestions}
          maxPointsPerQ={1000}
          highlightPlayerId={view === 'student' ? playerId : null}
          compact={view === 'student'}
          maxLanes={view === 'teacher' ? 8 : 5}
        />
      )}

      {/* Question screen */}
      <AnimatePresence mode="wait">
        <motion.div
          key={`qcard-${questionIndex}`}
          initial={{ opacity: 0, y: 30, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.98 }}
          transition={{ type: 'spring', stiffness: 260, damping: 22 }}
          className="arcade-screen"
        >
          <h2 className="arcade-screen__q">{question.question_text}</h2>
        </motion.div>
      </AnimatePresence>

      {/* Student: answer tiles */}
      {view === 'student' && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
          gap: 14,
        }}>
          {(question.options || []).map((opt, i) => (
            <AnswerTile
              key={`${questionIndex}-${i}`}
              index={i}
              opt={opt}
              color={TILE_COLORS[i]}
              selected={selected === opt}
              lastResult={lastResult}
              disabled={!!selected || remaining <= 0}
              onClick={() => { setSelected(opt); onAnswer?.(opt); }}
            />
          ))}
        </div>
      )}

      {/* Teacher: between-question leaderboard */}
      <AnimatePresence>
        {view === 'teacher' && showLeaderboard && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 280, damping: 22 }}
            style={{
              position: 'fixed', inset: 0, zIndex: 40,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: 24,
              background: 'rgba(5,5,16,0.78)',
              backdropFilter: 'blur(8px)',
            }}>
            <div className="arcade-screen" style={{ width: '100%', maxWidth: 460 }}>
              <div style={{
                fontFamily: "'Press Start 2P', system-ui, monospace",
                fontSize: 14, letterSpacing: 2,
                color: 'var(--arcade-mustard)',
                textAlign: 'center', marginBottom: 18,
                textShadow: '0 0 10px rgba(255,190,11,0.5)',
              }}>
                HIGH SCORES
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[...players].sort((a,b) => (b.score||0) - (a.score||0)).slice(0, 5).map((p, i) => (
                  <div key={p.player_id || i} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '8px 12px', borderRadius: 8,
                    background: i === 0 ? 'rgba(255,190,11,0.16)' : 'rgba(255,255,255,0.04)',
                    border: i === 0 ? '1px solid rgba(255,190,11,0.5)' : '1px solid rgba(255,255,255,0.08)',
                  }}>
                    <span style={{
                      fontFamily: "'Press Start 2P', monospace", fontSize: 10,
                      color: i === 0 ? '#FFBE0B' : 'var(--arcade-ink-dim)',
                    }}>
                      #{i + 1} {(p.name || 'PLAYER').slice(0, 12).toUpperCase()}
                    </span>
                    <span className="arcade-led-num" style={{ fontSize: 12 }}>
                      {p.score || 0}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Student result splash (full-screen, brief) */}
      <AnimatePresence>
        {view === 'student' && splash && (
          <motion.div
            key={`splash-${questionIndex}-${splash.kind}`}
            initial={{ opacity: 0, scale: 0.4 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 340, damping: 20 }}
            className="arcade-splash"
          >
            <div className={`arcade-splash__text arcade-splash__text--${splash.kind}`}>
              {splash.kind === 'win' ? `+${splash.points || 0}` : 'X'}
              {splash.kind === 'lose' && splash.correctLetter && (
                <div style={{ fontSize: 18, marginTop: 16, color: '#FFBE0B' }}>
                  ANSWER: {splash.correctLetter}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ---------- Answer tile ---------- */

function AnswerTile({ index, opt, color, selected, lastResult, disabled, onClick }) {
  const isCorrect = lastResult && lastResult.correct_answer === opt;
  const isWrongSelected = lastResult && selected && !lastResult.correct && selected === opt;
  const revealed = !!lastResult;

  const cls = [
    'arcade-btn',
    revealed && isCorrect        ? 'arcade-btn--correct' : '',
    revealed && isWrongSelected  ? 'arcade-btn--wrong'   : '',
    revealed && !isCorrect && !isWrongSelected ? 'arcade-btn--dim' : '',
  ].filter(Boolean).join(' ');

  return (
    <motion.button
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.12 + index * 0.07, duration: 0.35 }}
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      disabled={disabled}
      onClick={onClick}
      aria-pressed={selected}
      className={cls}
      style={{ '--btn-color': color }}
    >
      <span className="arcade-btn__cap">{String.fromCharCode(65 + index)}</span>
      <span className="arcade-btn__label">{opt}</span>
      {revealed && isCorrect && <CheckCircle style={{ width: 22, height: 22, flexShrink: 0 }} />}
      {revealed && isWrongSelected && <XCircle style={{ width: 22, height: 22, flexShrink: 0 }} />}
    </motion.button>
  );
}

function findLetter(options, answer) {
  if (!options || !answer) return '';
  const idx = options.findIndex(o => o === answer);
  return idx >= 0 ? String.fromCharCode(65 + idx) : '';
}
