'use client';
import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { CheckCircle, Trophy, Star, Zap, Hash } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { play } from '@/lib/gameSounds';
import { correctAnswer, winnerCelebration } from '@/lib/confetti';
import { ArcadeChip } from '@/components/games/CabinetStage';

/**
 * Bingo Blitz — arcade-cabinet edition (v2 April 2026).
 *
 * 50s bingo-hall / diner neon theme: hot pink #FF006E accent,
 * glossy tiles with dauber-stamp ink-splat animation on mark,
 * bingo ball caller display, winning-line glow, confetti burst.
 *
 * Props:
 *   allQuestions: [{ question_text, answer, options }]
 *   question:     current teacher-called question
 *   view:         'student' | 'teacher'
 *   config:       { board_size: 3|4|5, free_space: bool }
 *   playerId:     stable id for deterministic card shuffle
 *   onBingo:      () => void — student claims bingo
 *   onCallNext:   () => void — teacher advances to next call
 *   calledAnswers: string[] — already-called answer terms
 *   players:      player roster (for HUD display)
 */

const DAUBER_COLORS = [
  '#FF006E', '#FF3864', '#E6194B', '#FF1493', '#FF69B4',
];

export default function BingoBlitz({
  allQuestions = [], question, view = 'student', config = {},
  playerId = 'anon', onBingo, onCallNext, calledAnswers = [],
  players = [], lastResult = null, bingoWinner = null,
}) {
  const size = config.board_size || 5;
  const freeSpace = config.free_space !== false;
  const total = size * size;

  // Build a deterministic card per player
  const card = useMemo(() => {
    const answers = allQuestions.map(q => q.answer).filter(Boolean);
    const shuffled = seededShuffle([...answers], playerId).slice(0, total);
    while (shuffled.length < total) shuffled.push('');
    const grid = [];
    for (let r = 0; r < size; r++) {
      grid.push(shuffled.slice(r * size, (r + 1) * size));
    }
    if (freeSpace && size % 2 === 1) {
      const mid = Math.floor(size / 2);
      grid[mid][mid] = 'FREE';
    }
    return grid;
  }, [allQuestions, size, freeSpace, playerId, total]);

  const [marked, setMarked] = useState(() => new Set(freeSpace && size % 2 === 1 ? ['FREE'] : []));
  const [hasWon, setHasWon] = useState(false);
  const [winningLine, setWinningLine] = useState(null); // Set of cell indices that form the bingo
  const [recentMark, setRecentMark] = useState(null); // index of cell just stamped (for animation)
  const [newCallFlash, setNewCallFlash] = useState(false); // flash when teacher calls new answer

  // Detect new call from teacher
  const prevCalledCount = useRef(calledAnswers.length);
  useEffect(() => {
    if (calledAnswers.length > prevCalledCount.current) {
      setNewCallFlash(true);
      play('whoosh');
      setTimeout(() => setNewCallFlash(false), 600);
    }
    prevCalledCount.current = calledAnswers.length;
  }, [calledAnswers.length]);

  // Check for bingo after each mark
  useEffect(() => {
    if (hasWon) return;
    const result = checkBingo(card, marked, size);
    if (result) {
      setHasWon(true);
      setWinningLine(result);
      play('bingo');
      winnerCelebration();
      onBingo?.();
    }
  }, [marked, card, size, hasWon, onBingo]);

  // Compute near-miss cells — cells belonging to any line with (size-1) marks.
  // These pulse gold to tease the "one away" moment.
  const nearMissCells = useMemo(() => {
    if (hasWon) return new Set();
    const nearMiss = new Set();
    const threshold = size - 1;
    // Rows
    for (let r = 0; r < size; r++) {
      const markedCount = card[r].filter(c => marked.has(c)).length;
      if (markedCount === threshold) {
        card[r].forEach((_, c) => {
          if (!marked.has(card[r][c])) nearMiss.add(r * size + c);
        });
      }
    }
    // Cols
    for (let c = 0; c < size; c++) {
      const markedCount = card.filter(row => marked.has(row[c])).length;
      if (markedCount === threshold) {
        for (let r = 0; r < size; r++) {
          if (!marked.has(card[r][c])) nearMiss.add(r * size + c);
        }
      }
    }
    // Diag TL-BR
    const d1 = card.filter((row, i) => marked.has(row[i])).length;
    if (d1 === threshold) {
      for (let i = 0; i < size; i++) {
        if (!marked.has(card[i][i])) nearMiss.add(i * size + i);
      }
    }
    // Diag TR-BL
    const d2 = card.filter((row, i) => marked.has(row[size - 1 - i])).length;
    if (d2 === threshold) {
      for (let i = 0; i < size; i++) {
        if (!marked.has(card[i][size - 1 - i])) nearMiss.add(i * size + (size - 1 - i));
      }
    }
    return nearMiss;
  }, [card, marked, size, hasWon]);

  // Dauber color per player (seeded)
  const dauberColor = useMemo(() => {
    let h = 0;
    for (let i = 0; i < playerId.length; i++) h = ((h << 5) - h + playerId.charCodeAt(i)) | 0;
    return DAUBER_COLORS[Math.abs(h) % DAUBER_COLORS.length];
  }, [playerId]);

  const toggleCell = useCallback((term, cellIndex) => {
    if (!term || hasWon) return;
    if (term !== 'FREE' && !calledAnswers.includes(term)) return;
    const next = new Set(marked);
    if (next.has(term)) {
      next.delete(term);
    } else {
      next.add(term);
      setRecentMark(cellIndex);
      play('correct');
      setTimeout(() => setRecentMark(null), 500);
    }
    setMarked(next);
  }, [marked, calledAnswers, hasWon]);

  // Closest to bingo: count best line progress
  const bestLineProgress = useMemo(() => {
    let best = 0;
    // Rows
    for (let r = 0; r < size; r++) {
      const count = card[r].filter(c => marked.has(c)).length;
      if (count > best) best = count;
    }
    // Cols
    for (let c = 0; c < size; c++) {
      const count = card.filter(row => marked.has(row[c])).length;
      if (count > best) best = count;
    }
    // Diags
    const d1 = card.filter((row, i) => marked.has(row[i])).length;
    const d2 = card.filter((row, i) => marked.has(row[size - 1 - i])).length;
    best = Math.max(best, d1, d2);
    return best;
  }, [card, marked, size]);

  // Latest called answer (the "ball")
  const currentBall = calledAnswers.length > 0 ? calledAnswers[calledAnswers.length - 1] : null;

  // Question lookup for teacher: map answer → question_text
  const answerToQuestion = useMemo(() => {
    const map = {};
    allQuestions.forEach(q => { if (q.answer) map[q.answer] = q.question_text; });
    return map;
  }, [allQuestions]);

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>

      {/* ── Bingo Ball Caller Display ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: 16, marginBottom: 16,
      }}>
        {/* Current call ball */}
        <AnimatePresence mode="wait">
          {question && (
            <motion.div
              key={`call-${calledAnswers.length}`}
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              exit={{ scale: 0, rotate: 180 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
              style={{
                width: 100, height: 100,
                borderRadius: '50%',
                background: `radial-gradient(circle at 35% 35%, #FF4D8E, #FF006E 50%, #C8005A 100%)`,
                boxShadow: `0 0 30px rgba(255,0,110,0.5), inset 0 -4px 12px rgba(0,0,0,0.3), inset 0 4px 8px rgba(255,255,255,0.2)`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column',
                flexShrink: 0,
              }}
            >
              <span style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 8, color: 'rgba(255,255,255,0.7)',
                letterSpacing: 1, marginBottom: 2,
              }}>CALL #{calledAnswers.length}</span>
              <span style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 28, color: '#fff',
                textShadow: '0 0 8px rgba(255,255,255,0.6)',
              }}>
                {calledAnswers.length}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Question text */}
        <div style={{ flex: 1 }}>
          {question ? (
            <motion.div
              key={`q-${calledAnswers.length}`}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="arcade-screen"
              style={{
                padding: '16px 20px',
                borderColor: '#FF006E',
                boxShadow: newCallFlash
                  ? '0 0 30px rgba(255,0,110,0.6), 0 0 60px rgba(255,0,110,0.2)'
                  : '0 0 16px rgba(255,0,110,0.2)',
                transition: 'box-shadow 0.3s ease',
              }}
            >
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 8, letterSpacing: 2,
                color: '#FF006E', marginBottom: 8,
                textTransform: 'uppercase',
              }}>
                TEACHER ASKS
              </div>
              <div style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 18, fontWeight: 600,
                color: '#F7F7FF', lineHeight: 1.4,
              }}>
                {question.question_text}
              </div>
              {view === 'teacher' && (
                <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'center' }}>
                  <span style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 9, padding: '6px 12px', borderRadius: 8,
                    background: 'rgba(22,212,116,0.12)',
                    border: '1px solid rgba(22,212,116,0.4)',
                    color: '#16D474',
                  }}>
                    ANSWER: {question.answer}
                  </span>
                  <button onClick={onCallNext}
                    className="arcade-btn"
                    style={{
                      '--btn-color': '#FF006E',
                      display: 'inline-flex',
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 9,
                    }}>
                    <span className="arcade-btn__cap"><Zap style={{ width: 10, height: 10 }} /></span>
                    <span className="arcade-btn__label">CALL NEXT</span>
                  </button>
                </div>
              )}
            </motion.div>
          ) : (
            <div style={{
              padding: '20px',
              textAlign: 'center',
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 10, color: 'rgba(247,247,255,0.35)',
              letterSpacing: 1,
            }}>
              WAITING FOR FIRST CALL...
            </div>
          )}
        </div>
      </div>

      {/* ── HUD: progress + stats ── */}
      <div className="arcade-hud" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ArcadeChip>{calledAnswers.length} / {total} called</ArcadeChip>
          {view === 'student' && (
            <span style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 8, letterSpacing: 1,
              padding: '5px 10px', borderRadius: 6,
              background: bestLineProgress >= size - 1
                ? 'rgba(255,0,110,0.2)'
                : 'rgba(255,255,255,0.06)',
              border: bestLineProgress >= size - 1
                ? '1px solid rgba(255,0,110,0.5)'
                : '1px solid rgba(255,255,255,0.08)',
              color: bestLineProgress >= size - 1 ? '#FF006E' : 'rgba(247,247,255,0.55)',
              animation: bestLineProgress >= size - 1 ? 'pulse 1s infinite' : 'none',
            }}>
              {hasWon ? '🎉 BINGO!' : `${bestLineProgress}/${size} BEST LINE`}
            </span>
          )}
          <ArcadeChip>{marked.size} stamped</ArcadeChip>
        </div>
        {players.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {players.slice(0, 6).map((p, i) => (
              <span key={p.player_id || i} style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 8, letterSpacing: 1,
                padding: '5px 8px', borderRadius: 6,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(247,247,255,0.55)',
              }}>
                {p.avatar || '🐻'} {(p.name || '').slice(0, 8)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Student's Bingo Card ── */}
      {view === 'student' && (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))`,
            gap: 6,
            marginBottom: 14,
            padding: 12,
            background: 'rgba(255,0,110,0.04)',
            border: '2px solid rgba(255,0,110,0.15)',
            borderRadius: 14,
            boxShadow: 'inset 0 2px 12px rgba(0,0,0,0.3)',
          }}>
            {card.flat().map((term, i) => {
              const isMarked = marked.has(term);
              const isCalled = term === 'FREE' || calledAnswers.includes(term);
              const isFree = term === 'FREE';
              const isWinCell = winningLine?.has(i);
              const isRecent = recentMark === i;
              const isNearMiss = nearMissCells.has(i);

              return (
                <motion.button
                  key={i}
                  onClick={() => toggleCell(term, i)}
                  disabled={!isCalled || hasWon}
                  whileHover={isCalled && !hasWon ? { scale: 1.05 } : {}}
                  whileTap={isCalled && !hasWon ? { scale: 0.95 } : {}}
                  style={{
                    position: 'relative',
                    aspectRatio: '1',
                    borderRadius: 10,
                    border: isWinCell
                      ? '2px solid #FF006E'
                      : isNearMiss
                        ? '2px solid #FFBE0B'
                        : isMarked
                          ? `2px solid ${dauberColor}`
                          : isCalled
                            ? '2px solid rgba(255,0,110,0.35)'
                            : '2px solid rgba(255,255,255,0.06)',
                    background: isWinCell
                      ? 'rgba(255,0,110,0.25)'
                      : isNearMiss
                        ? 'rgba(255,190,11,0.12)'
                        : isMarked
                          ? isFree
                            ? 'rgba(255,190,11,0.25)'
                            : `rgba(255,0,110,0.15)`
                          : isCalled
                            ? 'rgba(255,0,110,0.06)'
                            : 'rgba(255,255,255,0.02)',
                    color: isMarked
                      ? '#F7F7FF'
                      : isCalled
                        ? 'rgba(247,247,255,0.85)'
                        : 'rgba(247,247,255,0.35)',
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: size <= 3 ? 13 : size <= 4 ? 11 : 10,
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                    lineHeight: 1.2,
                    padding: 4,
                    cursor: isCalled && !hasWon ? 'pointer' : 'not-allowed',
                    opacity: isCalled ? 1 : 0.45,
                    overflow: 'hidden',
                    boxShadow: isWinCell
                      ? '0 0 16px rgba(255,0,110,0.5), inset 0 0 12px rgba(255,0,110,0.2)'
                      : isNearMiss
                        ? '0 0 14px rgba(255,190,11,0.45), inset 0 0 10px rgba(255,190,11,0.18)'
                        : isMarked
                          ? `inset 0 0 12px rgba(255,0,110,0.15)`
                          : 'inset 0 2px 4px rgba(0,0,0,0.2)',
                    transition: 'all 0.2s ease',
                    animation: isNearMiss ? 'nearMissPulse 1.3s ease-in-out infinite' : 'none',
                    wordBreak: 'break-word',
                  }}
                >
                  {/* Dauber ink stamp overlay */}
                  {isMarked && !isFree && (
                    <motion.div
                      initial={isRecent ? { scale: 0, opacity: 0 } : { scale: 1, opacity: 1 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                      style={{
                        position: 'absolute',
                        inset: 0,
                        borderRadius: '50%',
                        background: `radial-gradient(circle at 40% 40%, ${dauberColor}66, ${dauberColor}33 60%, transparent 70%)`,
                        pointerEvents: 'none',
                      }}
                    />
                  )}

                  {/* Free space star */}
                  {isFree ? (
                    <span style={{
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 9, color: '#FFBE0B',
                      textShadow: '0 0 6px rgba(255,190,11,0.6)',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                    }}>
                      <Star style={{ width: 14, height: 14 }} />
                      FREE
                    </span>
                  ) : (
                    <span style={{ position: 'relative', zIndex: 1 }}>
                      {term || '—'}
                    </span>
                  )}

                  {/* Checkmark on marked */}
                  {isMarked && !isFree && (
                    <motion.div
                      initial={isRecent ? { scale: 0 } : { scale: 1 }}
                      animate={{ scale: 1 }}
                      style={{
                        position: 'absolute', top: 3, right: 3,
                        width: 14, height: 14, borderRadius: '50%',
                        background: dauberColor,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        zIndex: 2,
                      }}
                    >
                      <CheckCircle style={{ width: 10, height: 10, color: '#fff' }} />
                    </motion.div>
                  )}
                </motion.button>
              );
            })}
          </div>

          {/* BINGO win banner */}
          <AnimatePresence>
            {hasWon && (
              <motion.div
                initial={{ opacity: 0, scale: 0.7, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ type: 'spring', stiffness: 300, damping: 18 }}
                style={{
                  padding: '18px 24px',
                  borderRadius: 14,
                  textAlign: 'center',
                  background: 'linear-gradient(135deg, #FF006E, #FF3864, #FF006E)',
                  boxShadow: '0 0 40px rgba(255,0,110,0.5), 0 8px 32px rgba(0,0,0,0.4)',
                  border: '2px solid rgba(255,255,255,0.2)',
                }}
              >
                <div style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 28, color: '#fff',
                  textShadow: '0 0 16px rgba(255,255,255,0.6), 0 4px 0 rgba(0,0,0,0.3)',
                  letterSpacing: 6,
                }}>
                  <Trophy style={{ width: 28, height: 28, display: 'inline', verticalAlign: 'middle', marginRight: 8 }} />
                  BINGO!
                </div>
                <div style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 14, color: 'rgba(255,255,255,0.8)',
                  marginTop: 6,
                }}>
                  You got a line! Great work!
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}

      {/* ── Teacher Monitor: called answers as bingo balls ── */}
      {view === 'teacher' && (
        <div style={{
          padding: 16,
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12,
        }}>
          <div style={{
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 8, letterSpacing: 2,
            color: 'rgba(247,247,255,0.4)',
            marginBottom: 10,
            textTransform: 'uppercase',
          }}>
            CALLED ANSWERS ({calledAnswers.length})
          </div>
          {calledAnswers.length === 0 ? (
            <div style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 13, color: 'rgba(247,247,255,0.35)',
            }}>
              Click "Call Next" to begin the game.
            </div>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {calledAnswers.map((a, i) => (
                <motion.div
                  key={i}
                  initial={i === calledAnswers.length - 1 ? { scale: 0, rotate: -90 } : {}}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                  style={{
                    width: 48, height: 48,
                    borderRadius: '50%',
                    background: i === calledAnswers.length - 1
                      ? `radial-gradient(circle at 35% 35%, #FF4D8E, #FF006E 50%, #C8005A 100%)`
                      : `radial-gradient(circle at 35% 35%, #444, #2A2A2A 50%, #1A1A1A 100%)`,
                    boxShadow: i === calledAnswers.length - 1
                      ? '0 0 16px rgba(255,0,110,0.5), inset 0 -2px 6px rgba(0,0,0,0.3), inset 0 2px 4px rgba(255,255,255,0.2)'
                      : 'inset 0 -2px 6px rgba(0,0,0,0.4), inset 0 2px 4px rgba(255,255,255,0.1)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexDirection: 'column',
                  }}
                  title={`#${i + 1}: ${a}`}
                >
                  <span style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 6, color: 'rgba(255,255,255,0.5)',
                  }}>{i + 1}</span>
                  <span style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: 7, fontWeight: 700,
                    color: '#fff',
                    maxWidth: 40,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    textAlign: 'center',
                  }}>{a}</span>
                </motion.div>
              ))}
            </div>
          )}

          {/* Teacher heat map: which answers are most/least marked (placeholder for future) */}
          <div style={{
            marginTop: 14,
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 7, letterSpacing: 1.5,
            color: 'rgba(247,247,255,0.25)',
            textTransform: 'uppercase',
          }}>
            {players.length} PLAYERS IN GAME
          </div>
        </div>
      )}

      {/* ── Teacher: winner modal when a student calls bingo ── */}
      <AnimatePresence>
        {view === 'teacher' && bingoWinner && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed', inset: 0, zIndex: 50,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: 24,
              background: 'rgba(5,5,16,0.82)',
              backdropFilter: 'blur(10px)',
            }}
          >
            <motion.div
              initial={{ scale: 0.6, rotate: -8, y: 20 }}
              animate={{ scale: 1, rotate: 0, y: 0 }}
              transition={{ type: 'spring', stiffness: 260, damping: 16 }}
              style={{
                maxWidth: 480, width: '100%',
                padding: 32,
                borderRadius: 20,
                textAlign: 'center',
                background: 'linear-gradient(135deg, #FF006E, #FF3864, #FF006E)',
                boxShadow: '0 0 60px rgba(255,0,110,0.6), 0 20px 60px rgba(0,0,0,0.5)',
                border: '3px solid rgba(255,255,255,0.25)',
              }}
            >
              <div style={{ fontSize: 64, marginBottom: 8 }}>
                {bingoWinner.player_avatar || '🐻'}
              </div>
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 32, color: '#fff', letterSpacing: 6,
                textShadow: '0 0 20px rgba(255,255,255,0.7), 0 4px 0 rgba(0,0,0,0.35)',
                marginBottom: 12,
              }}>
                BINGO!
              </div>
              <div style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 22, fontWeight: 700, color: '#fff',
              }}>
                {bingoWinner.player_name || 'A player'}
              </div>
              <div style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 13, color: 'rgba(255,255,255,0.78)',
                marginTop: 6,
              }}>
                just claimed a line!
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Student: other-player-won overlay (fills the card area) ── */}
      <AnimatePresence>
        {view === 'student' && bingoWinner && !hasWon && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed', inset: 0, zIndex: 40,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: 24,
              background: 'rgba(5,5,16,0.75)',
              backdropFilter: 'blur(6px)',
            }}
          >
            <motion.div
              initial={{ scale: 0.8, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 280, damping: 20 }}
              className="arcade-screen"
              style={{
                maxWidth: 380, width: '100%',
                padding: 28,
                textAlign: 'center',
                borderColor: '#FFBE0B',
              }}
            >
              <div style={{ fontSize: 56, marginBottom: 8 }}>
                {bingoWinner.player_avatar || '🐻'}
              </div>
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 14, letterSpacing: 2,
                color: '#FFBE0B',
                textShadow: '0 0 12px rgba(255,190,11,0.55)',
                marginBottom: 10,
              }}>
                {(bingoWinner.player_name || 'Someone').toUpperCase()}
              </div>
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 18, color: '#fff',
                letterSpacing: 3,
                marginBottom: 12,
              }}>
                GOT BINGO!
              </div>
              <div style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 13, color: 'rgba(247,247,255,0.7)',
              }}>
                Nice game — wait for the next round.
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <style jsx>{`
        @keyframes nearMissPulse {
          0%, 100% {
            box-shadow: 0 0 14px rgba(255,190,11,0.45), inset 0 0 10px rgba(255,190,11,0.18);
          }
          50% {
            box-shadow: 0 0 24px rgba(255,190,11,0.75), inset 0 0 16px rgba(255,190,11,0.28);
          }
        }
      `}</style>
    </div>
  );
}

/* ── Helpers ── */

function seededShuffle(arr, seed) {
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

/**
 * Returns a Set of cell indices forming the winning line, or null if no bingo.
 */
function checkBingo(card, marked, size) {
  // Rows
  for (let r = 0; r < size; r++) {
    if (card[r].every(c => marked.has(c))) {
      return new Set(card[r].map((_, c) => r * size + c));
    }
  }
  // Columns
  for (let c = 0; c < size; c++) {
    if (card.every(row => marked.has(row[c]))) {
      return new Set(card.map((_, r) => r * size + c));
    }
  }
  // Diagonal TL-BR
  if (card.every((row, i) => marked.has(row[i]))) {
    return new Set(card.map((_, i) => i * size + i));
  }
  // Diagonal TR-BL
  if (card.every((row, i) => marked.has(row[size - 1 - i]))) {
    return new Set(card.map((_, i) => i * size + (size - 1 - i)));
  }
  return null;
}
