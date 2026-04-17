'use client';
import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, Star, Users, Zap, Minus } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer } from '@/lib/confetti';
import { ArcadeChip } from '@/components/games/CabinetStage';

/**
 * Jeopardy — arcade-cabinet edition (v2.2 April 2026 — real wagering).
 *
 * Backend-synced Jeopardy scoring:
 *   - Every answer sends a `wager` with the answer. For regular cells wager =
 *     cell value; for Daily Double it's the student's locked wager.
 *   - Server applies correct → +wager / wrong → -wager, updates player.score.
 *   - Scores can go negative; scoreboard reads from player.score (backend).
 *
 * Daily Double: only the current score leader answers. Wager range is
 * [$5, max(score, highest remaining value)]. Everyone else sees a "waiting"
 * panel while the leader plays.
 *
 * Visual direction: royal navy #0A1F4E board, gold #E6B800 serif cells,
 * spotlight vignette on current cell, category column glow on pick,
 * velvet curtain edge glow.
 */

const VALUES = [200, 400, 600, 800, 1000];
const TILE_COLORS = ['#FF3864', '#3A86FF', '#FFBE0B', '#2EC4B6'];

export default function Jeopardy({
  question, players = [], view = 'student', onAnswer, onPickCell,
  config = {}, questionIndex = 0, totalQuestions = 25, answeredCells = [],
  allQuestions = [], lastResult = null, playerId = null,
}) {
  const categories = useMemo(() => {
    const cats = (config.categories || 'Vocab, Facts, Events, People, Dates')
      .split(',').map(c => c.trim()).slice(0, 5);
    while (cats.length < 5) cats.push(`Category ${cats.length + 1}`);
    return cats;
  }, [config.categories]);

  const hasDailyDouble = config.daily_double !== false;

  // Deterministic Daily Double position (seeded from categories hash).
  const ddIndex = useMemo(() => {
    if (!hasDailyDouble) return -1;
    let hash = 0;
    const seed = (config.categories || 'default');
    for (let i = 0; i < seed.length; i++) hash = ((hash << 5) - hash + seed.charCodeAt(i)) | 0;
    return Math.abs(hash) % 25;
  }, [config.categories, hasDailyDouble]);

  // Build the 5×5 board: 5 columns (categories), 5 rows (values)
  const board = useMemo(() => {
    const grid = Array(5).fill(0).map(() => Array(5).fill(null));
    (allQuestions || []).slice(0, 25).forEach((q, idx) => {
      const col = idx % 5;
      const row = Math.floor(idx / 5);
      if (row < 5 && col < 5) {
        grid[row][col] = { ...q, index: idx, value: VALUES[row], isDailyDouble: idx === ddIndex };
      }
    });
    return grid;
  }, [allQuestions, ddIndex]);

  const [selected, setSelected] = useState(null);
  const [wagerMode, setWagerMode] = useState(false);
  const [wagerAmount, setWagerAmount] = useState(0);
  const [wagerInput, setWagerInput] = useState(''); // free-form text input for wager
  const [scorePopup, setScorePopup] = useState(null);
  // Wager locked-in for the CURRENT question. Regular cells auto-lock at cell
  // value; DD waits for the student to submit the wager modal.
  const [lockedWager, setLockedWager] = useState(0);

  const currentCell = board.flat().find(c => c && c.index === questionIndex);
  const currentCol = currentCell ? currentCell.index % 5 : -1;
  const isFinalJeopardy = questionIndex === 24 && totalQuestions >= 25;
  const isCurrentDD = !!(currentCell?.isDailyDouble && !answeredCells.includes(questionIndex));

  // Backend is the source of truth. player.score reflects Jeopardy dollars for
  // this game shell (wager-driven scoring on the server side).
  const myScore = playerId ? (players.find(p => p.player_id === playerId)?.score || 0) : 0;

  // Highest remaining cell value on the board (for wager ceiling)
  const highestRemainingValue = useMemo(() => {
    const remaining = board.flat().filter(c => c && !answeredCells.includes(c.index));
    return remaining.length > 0 ? Math.max(...remaining.map(c => c.value)) : 1000;
  }, [board, answeredCells]);

  // Wager ceiling: max of (player's score, highest remaining value). Min $5.
  const wagerCeiling = Math.max(myScore, highestRemainingValue, 5);

  // ── Daily Double leader-only gate ──
  // The leader is the player with the highest current score. Ties broken by
  // first-seen. Only the leader sees the wager modal + answer tiles on DD.
  const leaderId = useMemo(() => {
    if (players.length === 0) return null;
    return [...players].sort((a, b) => (b.score || 0) - (a.score || 0))[0]?.player_id || null;
  }, [players]);
  const amLeader = playerId && leaderId === playerId;
  const leaderName = useMemo(() => players.find(p => p.player_id === leaderId)?.name || 'the leader', [players, leaderId]);

  // Quick-wager presets for the DD modal
  const wagerPresets = useMemo(() => {
    const presets = [];
    const cellVal = currentCell?.value || 200;
    presets.push({ label: `Cell ($${cellVal})`, value: cellVal });
    const halfScore = Math.floor(myScore / 2);
    if (halfScore > cellVal && halfScore > 0) {
      presets.push({ label: `Half ($${halfScore})`, value: halfScore });
    }
    if (wagerCeiling > cellVal) {
      presets.push({ label: `MAX ($${wagerCeiling})`, value: wagerCeiling });
    }
    return presets;
  }, [currentCell?.value, myScore, wagerCeiling]);

  // Reset per-question state. Regular cells auto-lock wager at cell value so
  // the student can answer immediately. DD cells hold until the student
  // submits the wager modal.
  useEffect(() => {
    setSelected(null);
    if (isCurrentDD) {
      setWagerMode(true);
      const cellVal = currentCell?.value || 200;
      const def = Math.min(cellVal, wagerCeiling);
      setWagerAmount(def);
      setWagerInput(String(def));
      setLockedWager(0);
    } else {
      setWagerMode(false);
      setLockedWager(currentCell?.value || 200);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question?.question_text, questionIndex]);

  // DD reveal SFX — fire once per new DD question
  const ddPlayedForRef = useRef(null);
  useEffect(() => {
    if (isCurrentDD && question && ddPlayedForRef.current !== questionIndex) {
      ddPlayedForRef.current = questionIndex;
      play('ddReveal');
    }
  }, [isCurrentDD, question, questionIndex]);

  // Detect cell closure → ding + dollar popup
  const prevAnswered = useRef(answeredCells);
  useEffect(() => {
    const newClosed = answeredCells.filter(i => !prevAnswered.current.includes(i));
    if (newClosed.length > 0) {
      play('correct');
      const idx = newClosed[newClosed.length - 1];
      const cell = board.flat().find(c => c && c.index === idx);
      if (cell) setScorePopup({ index: idx, text: `$${cell.value}` });
      setTimeout(() => { setScorePopup(null); }, 1200);
    }
    prevAnswered.current = answeredCells;
  }, [answeredCells, board]);

  // Confetti on personal correct result (backend already updated the score).
  useEffect(() => {
    if (lastResult?.correct) correctAnswer({ x: 0.5, y: 0.55 });
  }, [lastResult]);

  // Lock the wager and dismiss the modal (DD only — regular cells auto-lock).
  const lockWager = useCallback(() => {
    const clamped = Math.max(5, Math.min(wagerAmount, wagerCeiling));
    setLockedWager(clamped);
    setWagerAmount(clamped);
    setWagerMode(false);
    play('whoosh');
  }, [wagerAmount, wagerCeiling]);

  // Handle wager text input
  const handleWagerInput = useCallback((val) => {
    const cleaned = val.replace(/[^0-9]/g, '');
    setWagerInput(cleaned);
    const num = parseInt(cleaned, 10);
    if (!isNaN(num) && num >= 0) {
      setWagerAmount(Math.min(num, wagerCeiling));
    }
  }, [wagerCeiling]);

  const cellsRemaining = 25 - answeredCells.length;

  // Scoreboard is driven directly by backend-synced player.score (dollars).
  const rankedPlayers = useMemo(() => {
    return [...players]
      .map(p => ({ ...p, jScore: p.score || 0 }))
      .sort((a, b) => b.jScore - a.jScore);
  }, [players]);

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* ── Board header: category names ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6,
        marginBottom: 6,
      }}>
        {categories.map((cat, i) => {
          const isActive = i === currentCol && !!question;
          return (
            <div key={i} style={{
              background: isActive
                ? 'linear-gradient(180deg, #E6B800 0%, #A88200 100%)'
                : 'linear-gradient(180deg, #1A3A7A 0%, #0A1F4E 100%)',
              border: isActive
                ? '1px solid #FFEF9E'
                : '1px solid rgba(230,184,0,0.35)',
              borderRadius: 8,
              padding: '10px 4px',
              textAlign: 'center',
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 8, letterSpacing: 1.5,
              color: isActive ? '#0A1F4E' : '#E6B800',
              textShadow: isActive
                ? '0 0 4px rgba(255,239,158,0.8)'
                : '0 0 6px rgba(230,184,0,0.5)',
              textTransform: 'uppercase',
              boxShadow: isActive
                ? '0 0 18px rgba(230,184,0,0.7), inset 0 0 8px rgba(255,239,158,0.4)'
                : 'none',
              transition: 'all 0.25s ease',
            }}>
              {cat}
            </div>
          );
        })}
      </div>

      {/* ── 5×5 board ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6,
        marginBottom: 14,
      }}>
        {board.flat().map((cell, i) => {
          if (!cell) return <div key={i} style={{ aspectRatio: '4/3', background: '#0A1030', borderRadius: 8 }} />;
          const isAnswered = answeredCells.includes(cell.index);
          const isCurrent = questionIndex === cell.index && question;
          const inActiveCol = question && (cell.index % 5) === currentCol && !isCurrent;
          const clickable = view === 'teacher' && !isAnswered && !isCurrent;
          const popup = scorePopup?.index === cell.index ? scorePopup.text : null;

          return (
            <motion.button
              key={i}
              disabled={!clickable}
              onClick={() => clickable && onPickCell?.(cell.index)}
              whileHover={clickable ? { scale: 1.04 } : {}}
              whileTap={clickable ? { scale: 0.97 } : {}}
              style={{
                position: 'relative',
                aspectRatio: '4/3',
                borderRadius: 8,
                border: isCurrent
                  ? '2px solid #E6B800'
                  : inActiveCol
                    ? '1px solid rgba(230,184,0,0.55)'
                    : '1px solid rgba(230,184,0,0.18)',
                background: isCurrent
                  ? 'radial-gradient(circle at center, rgba(230,184,0,0.25), #0A1F4E 70%)'
                  : isAnswered
                    ? '#080E22'
                    : inActiveCol
                      ? 'linear-gradient(180deg, #1A3A7A 0%, #0F2761 100%)'
                      : 'linear-gradient(180deg, #122B6B 0%, #0A1F4E 100%)',
                color: isAnswered ? 'rgba(230,184,0,0.25)' : '#E6B800',
                fontFamily: "'Press Start 2P', monospace",
                fontSize: isAnswered ? 10 : 16,
                fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: clickable ? 'pointer' : 'default',
                opacity: isAnswered ? 0.35 : 1,
                boxShadow: isCurrent
                  ? '0 0 20px rgba(230,184,0,0.35), inset 0 0 30px rgba(230,184,0,0.08)'
                  : inActiveCol
                    ? '0 0 10px rgba(230,184,0,0.18), inset 0 2px 6px rgba(0,0,0,0.4)'
                    : 'inset 0 2px 6px rgba(0,0,0,0.4)',
                overflow: 'hidden',
                textShadow: isAnswered ? 'none' : '0 0 8px rgba(230,184,0,0.6)',
                transition: 'background 0.25s ease, box-shadow 0.25s ease',
              }}
            >
              {isAnswered ? '✓' : `$${cell.value}`}
              {/* Daily Double badge (teacher sees it on unopened cells) */}
              {cell.isDailyDouble && !isAnswered && view === 'teacher' && (
                <span style={{
                  position: 'absolute', top: 3, right: 3,
                  background: '#FF3864', borderRadius: 4,
                  padding: '2px 4px', fontSize: 7,
                  color: '#fff', display: 'flex', alignItems: 'center', gap: 2,
                }}>
                  <Zap style={{ width: 8, height: 8 }} /> DD
                </span>
              )}
              {/* Dollar popup on cell close */}
              <AnimatePresence>
                {popup && (
                  <motion.span
                    initial={{ opacity: 0, y: 10, scale: 0.7 }}
                    animate={{ opacity: 1, y: -18, scale: 1.3 }}
                    exit={{ opacity: 0, y: -30 }}
                    transition={{ duration: 0.8 }}
                    style={{
                      position: 'absolute', top: '30%',
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 12, color: '#16D474',
                      textShadow: '0 0 8px rgba(22,212,116,0.8)',
                      pointerEvents: 'none',
                    }}
                  >
                    {popup}
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
          );
        })}
      </div>

      {/* ── HUD: cells remaining + Jeopardy scoreboard ── */}
      <div className="arcade-hud" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ArcadeChip>{cellsRemaining} left</ArcadeChip>
          {isFinalJeopardy && (
            <span className="arcade-hud-chip" style={{
              background: 'linear-gradient(135deg, #E6B800, #FF8A00)',
              color: '#0A0A18',
            }}>
              <Star style={{ width: 10, height: 10 }} /> FINAL JEOPARDY
            </span>
          )}
          {/* Show student their own score prominently */}
          {view === 'student' && playerId && (
            <span style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 10, letterSpacing: 1,
              padding: '5px 10px', borderRadius: 6,
              background: myScore >= 0
                ? 'rgba(230,184,0,0.16)'
                : 'rgba(255,56,100,0.12)',
              border: myScore >= 0
                ? '1px solid rgba(230,184,0,0.5)'
                : '1px solid rgba(255,56,100,0.4)',
              color: myScore >= 0 ? '#E6B800' : '#FF3864',
              textShadow: `0 0 6px ${myScore >= 0 ? 'rgba(230,184,0,0.5)' : 'rgba(255,56,100,0.5)'}`,
            }}>
              {myScore < 0 ? `-$${Math.abs(myScore).toLocaleString()}` : `$${myScore.toLocaleString()}`}
            </span>
          )}
        </div>
        {rankedPlayers.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {rankedPlayers.slice(0, 6).map((p, i) => {
              const isNeg = p.jScore < 0;
              return (
                <span key={p.player_id || i} style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 8, letterSpacing: 1,
                  padding: '5px 8px', borderRadius: 6,
                  background: i === 0 && !isNeg
                    ? 'rgba(230,184,0,0.16)'
                    : isNeg
                      ? 'rgba(255,56,100,0.08)'
                      : 'rgba(255,255,255,0.04)',
                  border: i === 0 && !isNeg
                    ? '1px solid rgba(230,184,0,0.5)'
                    : isNeg
                      ? '1px solid rgba(255,56,100,0.3)'
                      : '1px solid rgba(255,255,255,0.08)',
                  color: i === 0 && !isNeg ? '#E6B800' : isNeg ? '#FF3864' : 'var(--arcade-ink-dim)',
                }}>
                  {p.avatar || '🐻'} {(p.name || '').slice(0, 8)} {isNeg ? '-' : ''}${Math.abs(p.jScore).toLocaleString()}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Current question panel ── */}
      <AnimatePresence mode="wait">
        {question && (
          <motion.div
            key={`jq-${questionIndex}`}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 280, damping: 22 }}
            className="arcade-screen"
            style={{
              borderColor: '#E6B800',
              boxShadow: '0 0 0 1px rgba(0,0,0,0.6) inset, 0 0 24px rgba(230,184,0,0.25), 0 12px 40px rgba(0,0,0,0.55)',
            }}
          >
            {/* Category + value header */}
            <div style={{
              textAlign: 'center', marginBottom: 14,
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 9, letterSpacing: 2,
              color: '#E6B800',
              textShadow: '0 0 6px rgba(230,184,0,0.5)',
              textTransform: 'uppercase',
            }}>
              {categories[questionIndex % 5]} · ${VALUES[Math.floor(questionIndex / 5)] || 200}
              {currentCell?.isDailyDouble && (
                <span style={{ marginLeft: 10, color: '#FF3864' }}>⚡ DAILY DOUBLE</span>
              )}
            </div>

            <h2 className="arcade-screen__q" style={{ color: '#F7F7FF' }}>
              {question.question_text}
            </h2>

            {/* ── Daily Double: non-leader "waiting" screen ── */}
            {view === 'student' && isCurrentDD && !amLeader && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  marginTop: 20,
                  padding: 22, borderRadius: 12,
                  background: 'rgba(255,56,100,0.1)',
                  border: '1px solid rgba(255,56,100,0.4)',
                  textAlign: 'center',
                }}
              >
                <div style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 14, color: '#FF3864', marginBottom: 10,
                  textShadow: '0 0 8px rgba(255,56,100,0.6)',
                  letterSpacing: 2,
                }}>
                  ⚡ DAILY DOUBLE ⚡
                </div>
                <div style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 10, color: '#E6B800',
                  letterSpacing: 1.5, marginBottom: 6,
                }}>
                  {leaderName.toUpperCase()} ANSWERS
                </div>
                <div style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 13, color: 'rgba(247,247,255,0.65)',
                }}>
                  The score leader plays this one — sit tight and watch.
                </div>
              </motion.div>
            )}

            {/* ── Daily Double wager modal (leader only) ── */}
            <AnimatePresence>
              {view === 'student' && wagerMode && amLeader && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  style={{
                    marginTop: 20,
                    padding: 18, borderRadius: 12,
                    background: 'rgba(230,184,0,0.08)',
                    border: '1px solid rgba(230,184,0,0.35)',
                    textAlign: 'center',
                  }}
                >
                  <div style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 11, color: '#E6B800', marginBottom: 6,
                    textShadow: '0 0 6px rgba(230,184,0,0.5)',
                  }}>
                    ⚡ DAILY DOUBLE
                  </div>
                  <div style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: 13, color: 'rgba(247,247,255,0.65)', marginBottom: 14,
                  }}>
                    Wager $5 up to ${wagerCeiling.toLocaleString()}
                    {myScore !== 0 && <span> · Your score: ${myScore.toLocaleString()}</span>}
                  </div>

                  {/* Free-input wager field */}
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    gap: 8, marginBottom: 14,
                  }}>
                    <span style={{
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 18, color: '#E6B800',
                    }}>$</span>
                    <input
                      type="text"
                      inputMode="numeric"
                      value={wagerInput}
                      onChange={(e) => handleWagerInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && lockWager()}
                      autoFocus
                      style={{
                        width: 140,
                        padding: '10px 14px',
                        borderRadius: 8,
                        border: '2px solid rgba(230,184,0,0.5)',
                        background: 'rgba(10,31,78,0.8)',
                        color: '#E6B800',
                        fontFamily: "'Press Start 2P', monospace",
                        fontSize: 18,
                        textAlign: 'center',
                        outline: 'none',
                        caretColor: '#E6B800',
                      }}
                      placeholder="0"
                    />
                  </div>

                  {/* Quick-wager preset buttons */}
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 14 }}>
                    {wagerPresets.map((preset, idx) => {
                      const isActive = wagerAmount === preset.value;
                      return (
                        <button key={idx} onClick={() => {
                          setWagerAmount(preset.value);
                          setWagerInput(String(preset.value));
                        }}
                          style={{
                            fontFamily: "'Press Start 2P', monospace",
                            fontSize: 9, padding: '8px 14px',
                            borderRadius: 8, border: 'none', cursor: 'pointer',
                            background: isActive
                              ? 'linear-gradient(135deg, #E6B800, #FF8A00)'
                              : 'rgba(255,255,255,0.06)',
                            color: isActive ? '#0A0A18' : '#E6B800',
                            boxShadow: isActive ? '0 0 12px rgba(230,184,0,0.5)' : 'none',
                            transition: 'all 0.15s ease',
                          }}>
                          {preset.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Validation message */}
                  {(wagerAmount < 5 || wagerAmount > wagerCeiling) && wagerInput !== '' && (
                    <div style={{
                      fontFamily: "'Space Grotesk', sans-serif",
                      fontSize: 11, color: '#FF3864', marginBottom: 10,
                    }}>
                      {wagerAmount < 5 ? 'Minimum wager is $5' : `Maximum wager is $${wagerCeiling.toLocaleString()}`}
                    </div>
                  )}

                  <button
                    onClick={lockWager}
                    disabled={wagerAmount < 5 || wagerAmount > wagerCeiling}
                    className="arcade-btn"
                    style={{
                      '--btn-color': '#E6B800',
                      margin: '0 auto', display: 'inline-flex',
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 10,
                      opacity: (wagerAmount < 5 || wagerAmount > wagerCeiling) ? 0.4 : 1,
                    }}
                  >
                    <span className="arcade-btn__cap">⚡</span>
                    <span className="arcade-btn__label">LOCK WAGER: ${wagerAmount.toLocaleString()}</span>
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Answer tiles — hidden during DD wager modal; hidden entirely for
                non-leaders on a DD cell. */}
            {view === 'student' && !wagerMode && (!isCurrentDD || amLeader) && (
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                gap: 12, marginTop: 18,
              }}>
                {(question.options || []).map((opt, i) => {
                  const isCorrect = lastResult && lastResult.correct_answer === opt;
                  const isWrongSel = lastResult && selected === opt && !lastResult.correct;
                  const revealed = !!lastResult;
                  const cls = [
                    'arcade-btn',
                    revealed && isCorrect ? 'arcade-btn--correct' : '',
                    revealed && isWrongSel ? 'arcade-btn--wrong' : '',
                    revealed && !isCorrect && !isWrongSel ? 'arcade-btn--dim' : '',
                  ].filter(Boolean).join(' ');
                  return (
                    <motion.button
                      key={`${questionIndex}-${i}`}
                      initial={{ opacity: 0, y: 14 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 + i * 0.06, duration: 0.3 }}
                      disabled={!!selected}
                      onClick={() => {
                        setSelected(opt);
                        // Send the wager alongside the answer so the server
                        // applies Jeopardy scoring (correct +wager, wrong -wager).
                        onAnswer?.(opt, lockedWager);
                      }}
                      className={cls}
                      style={{ '--btn-color': TILE_COLORS[i] }}
                    >
                      <span className="arcade-btn__cap">{String.fromCharCode(65 + i)}</span>
                      <span className="arcade-btn__label">{opt}</span>
                      {revealed && isCorrect && <CheckCircle style={{ width: 20, height: 20, flexShrink: 0 }} />}
                      {revealed && isWrongSel && <XCircle style={{ width: 20, height: 20, flexShrink: 0 }} />}
                    </motion.button>
                  );
                })}
                {/* Show stake so student knows what's on the line */}
                <div style={{
                  gridColumn: '1 / -1',
                  textAlign: 'center',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 9, letterSpacing: 1.5,
                  color: 'rgba(230,184,0,0.65)',
                  marginTop: 4,
                }}>
                  {isCurrentDD ? '⚡ ' : ''}STAKE: ${lockedWager.toLocaleString()}
                </div>
              </div>
            )}

            {/* Teacher: show answer */}
            {view === 'teacher' && (
              <div style={{
                textAlign: 'center', marginTop: 16,
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 10, letterSpacing: 1.5,
                padding: '8px 14px', borderRadius: 8,
                background: 'rgba(22,212,116,0.12)',
                border: '1px solid rgba(22,212,116,0.4)',
                color: '#16D474',
                display: 'inline-block',
              }}>
                ANSWER: {question.answer}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Student result splash (shows dollar gain/loss) ── */}
      <AnimatePresence>
        {view === 'student' && lastResult && (!isCurrentDD || amLeader) && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              marginTop: 14,
              padding: '12px 16px', borderRadius: 10,
              textAlign: 'center',
              background: lastResult.correct ? 'rgba(22,212,116,0.12)' : 'rgba(255,56,100,0.10)',
              border: `1px solid ${lastResult.correct ? 'rgba(22,212,116,0.5)' : 'rgba(255,56,100,0.5)'}`,
            }}
          >
            {(() => {
              // Prefer the server-authoritative points; fall back to lockedWager.
              const delta = typeof lastResult.points === 'number' ? lastResult.points : (lastResult.correct ? lockedWager : -lockedWager);
              const sign = delta >= 0 ? '+' : '-';
              return (
                <span style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 12, letterSpacing: 1.5,
                  color: lastResult.correct ? '#16D474' : '#FF3864',
                  textShadow: `0 0 6px ${lastResult.correct ? 'rgba(22,212,116,0.5)' : 'rgba(255,56,100,0.5)'}`,
                }}>
                  {lastResult.correct
                    ? `CORRECT! ${sign}$${Math.abs(delta).toLocaleString()}`
                    : `WRONG ${sign}$${Math.abs(delta).toLocaleString()} · ANSWER: ${lastResult.correct_answer}`}
                </span>
              );
            })()}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
