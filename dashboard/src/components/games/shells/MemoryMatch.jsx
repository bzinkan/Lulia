'use client';
import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Flame, Sparkles, Eye } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer, winnerCelebration } from '@/lib/confetti';
import { ArcadeChip } from '@/components/games/CabinetStage';

/**
 * Memory Match — arcade-cabinet edition (v2 April 2026).
 *
 * Candlelit-purple theme (#8338EC accent from registry). Mystical rune tiles
 * on a dark-velvet board with candle flicker on unflipped tiles. Each pair
 * shares a glyph so the back reveal feels like uncovering a sigil.
 *
 * Renders inside CabinetStage. Interior content only — no full-page bg.
 *
 * Gaps fixed from v1:
 *   - Full CabinetStage integration with --arcade-accent per-game accent.
 *   - Configurable pair count (config.pair_count, 6–20; registry default 12).
 *   - Adaptive grid columns: ≤12 cards → 4 cols, ≤16 → 4, ≤24 → 6, ≤32 → 8, ≤40 → 8.
 *   - Streak multiplier: base 100pts, ×(1 + 0.5 × streak), capped at 3×, resets on miss.
 *     Live CURRENT streak chip + BEST streak chip.
 *   - Rune glyph on tile back: one of 20 mystical sigils — pair-matched runes
 *     give the reveal a "unlocked" feel instead of a generic "?".
 *   - Peek phase: all tiles flash their face for 2.5s at round start, then
 *     flip back — lets the student memorize a rough map before play begins.
 *   - Match celebration: flipped tiles glow gold, scale-up, then shrink back
 *     to the board as "matched" (not just disappear to a green state).
 *   - Teacher progress board: live per-student "matched / total" grid so the
 *     teacher can see who's close to done instead of a generic tagline.
 *   - Best-of-class banner when any student completes.
 *
 * Server contract unchanged: each successful match emits onAnswer(answer)
 * which hits the same MCQ channel as the other shells.
 */

// 20 mystical rune glyphs — seeded to pairs so each pair's back shows its own sigil.
// Unicode runic block is well-supported across fonts; fall back to an ASCII pair if needed.
const RUNES = [
  'ᚠ', 'ᚢ', 'ᚦ', 'ᚨ', 'ᚱ', 'ᚲ', 'ᚷ', 'ᚹ', 'ᚺ', 'ᚾ',
  'ᛁ', 'ᛃ', 'ᛇ', 'ᛈ', 'ᛉ', 'ᛊ', 'ᛏ', 'ᛒ', 'ᛖ', 'ᛗ',
];

// Streak multiplier tiers (capped at 3×).
function streakMultiplier(streak) {
  if (streak <= 1) return 1;
  if (streak === 2) return 1.5;
  if (streak === 3) return 2;
  if (streak === 4) return 2.5;
  return 3;
}

// Adaptive grid: pick a column count that keeps tiles roughly square-ish.
function gridColumns(cardCount) {
  if (cardCount <= 12) return 4;       // 6 pairs → 4×3
  if (cardCount <= 16) return 4;       // 8 pairs → 4×4
  if (cardCount <= 20) return 5;       // 10 pairs → 5×4
  if (cardCount <= 24) return 6;       // 12 pairs → 6×4
  if (cardCount <= 32) return 8;       // 16 pairs → 8×4
  return 8;                            // 20 pairs → 8×5
}

export default function MemoryMatch({
  allQuestions = [], question, players = [], view = 'student',
  onAnswer, config = {},
  questionIndex = 0, totalQuestions = 0, lastResult = null, playerId = 'anon',
}) {
  // Configurable pair count — registry default 12, min 6, max 20.
  const pairCount = useMemo(() => {
    const raw = parseInt(config.pair_count, 10);
    const requested = isNaN(raw) ? 12 : raw;
    const clamped = Math.max(6, Math.min(20, requested));
    const available = (allQuestions || []).length;
    return Math.min(clamped, Math.max(1, available)) || 6;
  }, [config.pair_count, allQuestions]);

  // Build deck: N Q/A pairs = 2N cards, each pair tagged with a rune glyph.
  const deck = useMemo(() => {
    const pairs = (allQuestions || []).slice(0, pairCount);
    const cards = [];
    pairs.forEach((q, i) => {
      const rune = RUNES[i % RUNES.length];
      cards.push({ id: `q${i}`, pairId: i, type: 'Q', rune, text: q.question_text, answer: q.answer });
      cards.push({ id: `a${i}`, pairId: i, type: 'A', rune, text: q.answer, answer: q.answer });
    });
    return seededShuffle(cards, playerId);
  }, [allQuestions, pairCount, playerId]);

  const cols = gridColumns(deck.length);

  const [flipped, setFlipped] = useState([]);          // [{id, pairId, ...}]
  const [matched, setMatched] = useState(new Set());
  const [matchBurst, setMatchBurst] = useState(null);  // pairId pulsing gold
  const [missShake, setMissShake] = useState(null);    // [cardId, cardId] briefly shaking
  const [misses, setMisses] = useState(0);
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [bestStreak, setBestStreak] = useState(0);
  const [peeking, setPeeking] = useState(false);       // round-start reveal
  const [startedAt] = useState(() => Date.now());
  const [endedAt, setEndedAt] = useState(null);
  const peekTimer = useRef(null);

  // ── Round-start peek phase ──
  // Flash every tile for 2.5s so students get a rough map, then flip back.
  useEffect(() => {
    if (view !== 'student') return;
    setPeeking(true);
    play('whoosh');
    peekTimer.current = setTimeout(() => setPeeking(false), 2500);
    return () => { if (peekTimer.current) clearTimeout(peekTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalPairs = deck.length / 2;
  const allMatched = matched.size === totalPairs && totalPairs > 0;

  // ── Complete: fanfare + time record ──
  useEffect(() => {
    if (allMatched && !endedAt) {
      setEndedAt(Date.now());
      play('fanfare');
      winnerCelebration();
    }
  }, [allMatched, endedAt]);

  const elapsedSec = useMemo(() => {
    const end = endedAt || Date.now();
    return Math.max(0, Math.round((end - startedAt) / 1000));
  }, [endedAt, startedAt]);

  function handleClick(card) {
    if (view !== 'student') return;
    if (peeking) return;
    if (matched.has(card.pairId)) return;
    if (flipped.length >= 2) return;
    if (flipped.some(f => f.id === card.id)) return;

    play('tick');
    const newFlipped = [...flipped, card];
    setFlipped(newFlipped);

    if (newFlipped.length === 2) {
      const [a, b] = newFlipped;
      if (a.pairId === b.pairId) {
        // MATCH!
        setTimeout(() => {
          const nextStreak = streak + 1;
          const mult = streakMultiplier(nextStreak);
          const points = Math.round(100 * mult);

          play('correct');
          correctAnswer({ x: 0.5, y: 0.5 });
          setMatched(prev => new Set([...prev, a.pairId]));
          setMatchBurst(a.pairId);
          setScore(s => s + points);
          setStreak(nextStreak);
          setBestStreak(b => Math.max(b, nextStreak));
          setFlipped([]);
          // Clear burst after the tile animates to matched state
          setTimeout(() => setMatchBurst(null), 800);

          // Report to server as a correct answer (MCQ channel)
          onAnswer?.(a.answer);
        }, 400);
      } else {
        // MISS — shake then flip back, reset streak
        setTimeout(() => {
          play('incorrect');
          setMissShake([a.id, b.id]);
          setMisses(m => m + 1);
          setStreak(0);
          setTimeout(() => {
            setFlipped([]);
            setMissShake(null);
          }, 500);
        }, 800);
      }
    }
  }

  // ── HUD slots ──
  const currentMult = streakMultiplier(streak);
  const hudLeft = (
    <>
      <ArcadeChip>MATCHED {matched.size}/{totalPairs}</ArcadeChip>
      <ArcadeChip variant="ghost">MISSES {misses}</ArcadeChip>
    </>
  );
  const hudRight = (
    <>
      <ArcadeChip variant={streak >= 2 ? 'solid' : 'ghost'}>
        STREAK ×{currentMult.toFixed(streak >= 2 ? 1 : 0).replace('.0', '')}
      </ArcadeChip>
      <ArcadeChip variant="ghost">BEST ×{streakMultiplier(bestStreak).toFixed(1).replace('.0', '')}</ArcadeChip>
      <ArcadeChip>SCORE {score}</ArcadeChip>
    </>
  );

  return (
    <div style={{ padding: '4px 0 24px', color: 'var(--arcade-ink, #F7F7FF)' }}>
      {/* HUD rendered as actual HUD band up top via CabinetStage would be ideal,
          but since shells are rendered inside the interior, we mirror the HUD
          chips here as a floating header so the shell works both standalone
          and inside CabinetStage. */}
      <StageHudBand left={hudLeft} right={hudRight} />

      <AnimatePresence mode="wait">
        {allMatched ? (
          <motion.div
            key="win"
            initial={{ opacity: 0, scale: 0.85, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 220, damping: 18 }}
            style={{
              maxWidth: 620, margin: '40px auto',
              padding: '36px 28px', textAlign: 'center',
              background: 'linear-gradient(180deg, rgba(131,56,236,0.2) 0%, rgba(10,10,24,0.85) 100%)',
              border: '2px solid var(--arcade-accent, #8338EC)',
              borderRadius: 18,
              boxShadow: '0 0 40px color-mix(in srgb, var(--arcade-accent, #8338EC) 40%, transparent)',
            }}
          >
            <div style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 12, letterSpacing: 2.5,
              color: 'var(--arcade-accent, #8338EC)', marginBottom: 12,
            }}>
              ★ ALL SIGILS BOUND ★
            </div>
            <div style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 26, letterSpacing: 2,
              color: '#F5C542', marginBottom: 16,
              textShadow: '0 0 18px rgba(245,197,66,0.6)',
            }}>
              {score} PTS
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
              <WinStat label="TIME" value={`${elapsedSec}s`} />
              <WinStat label="MISSES" value={misses} />
              <WinStat label="BEST STREAK" value={`×${streakMultiplier(bestStreak).toFixed(1).replace('.0', '')}`} />
            </div>
            <div style={{
              marginTop: 18,
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: 14, color: 'rgba(247,247,255,0.7)',
            }}>
              {misses === 0 ? 'Flawless — not a single miss.' : `${misses} miss${misses === 1 ? '' : 'es'} on the path.`}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="board"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{
              position: 'relative',
              maxWidth: 960, margin: '0 auto',
              padding: '22px 20px 28px',
              borderRadius: 18,
              border: '2px solid color-mix(in srgb, var(--arcade-accent, #8338EC) 55%, transparent)',
              background: `
                radial-gradient(circle at 50% 0%, rgba(131,56,236,0.18), transparent 60%),
                radial-gradient(circle at 10% 100%, rgba(245,197,66,0.08), transparent 55%),
                linear-gradient(180deg, #15102A 0%, #0B0818 100%)`,
              boxShadow: `
                0 0 28px color-mix(in srgb, var(--arcade-accent, #8338EC) 25%, transparent),
                0 12px 40px rgba(0,0,0,0.55)`,
            }}
          >
            {/* Peek indicator */}
            {peeking && view === 'student' && (
              <motion.div
                initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{
                  position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 10, letterSpacing: 2,
                  color: '#F5C542',
                  background: 'rgba(10,10,24,0.85)',
                  padding: '6px 14px', borderRadius: 999,
                  border: '1px solid rgba(245,197,66,0.4)',
                  display: 'flex', alignItems: 'center', gap: 6,
                  zIndex: 3,
                }}
              >
                <Eye style={{ width: 12, height: 12 }} /> MEMORIZE
              </motion.div>
            )}

            {/* Velvet grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${cols}, 1fr)`,
              gap: 10,
              marginTop: peeking ? 28 : 6,
            }}>
              {deck.map(card => {
                const isFlipped =
                  peeking ||
                  flipped.some(f => f.id === card.id) ||
                  matched.has(card.pairId);
                const isMatched = matched.has(card.pairId);
                const isBursting = matchBurst === card.pairId;
                const isShaking = missShake?.includes(card.id);
                return (
                  <RuneTile
                    key={card.id}
                    card={card}
                    flipped={isFlipped}
                    matched={isMatched}
                    bursting={isBursting}
                    shaking={isShaking}
                    onClick={() => handleClick(card)}
                  />
                );
              })}
            </div>

            {/* Bottom hint: streak bonus preview */}
            {streak >= 1 && view === 'student' && (
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                style={{
                  marginTop: 16,
                  textAlign: 'center',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 9, letterSpacing: 2,
                  color: streak >= 2 ? '#F5C542' : 'rgba(247,247,255,0.5)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                }}
              >
                <Flame style={{ width: 12, height: 12, color: streak >= 2 ? '#F5C542' : 'currentColor' }} />
                NEXT MATCH ×{streakMultiplier(streak + 1).toFixed(1).replace('.0', '')} = {Math.round(100 * streakMultiplier(streak + 1))} PTS
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Teacher view: per-student progress board */}
      {view === 'teacher' && (
        <TeacherProgress players={players} totalPairs={totalPairs} />
      )}

      {/* Student: after winning, show a "waiting on classmates" strip so
          early-finishers stay engaged instead of drifting off. */}
      {view === 'student' && allMatched && (
        <WaitingOnClassmates players={players} totalPairs={totalPairs} selfId={playerId} />
      )}
    </div>
  );
}

// ============================================================
//                     RuneTile component
// ============================================================

function RuneTile({ card, flipped, matched, bursting, shaking, onClick }) {
  return (
    <motion.button
      onClick={onClick}
      disabled={flipped}
      whileHover={!flipped ? { scale: 1.03, y: -2 } : {}}
      whileTap={!flipped ? { scale: 0.97 } : {}}
      animate={
        shaking
          ? { rotate: [0, -3, 3, -3, 3, 0], scale: [1, 1.04, 1] }
          : bursting
            ? { scale: [1, 1.12, 1], rotate: [0, 2, -2, 0] }
            : { rotateY: flipped ? 180 : 0 }
      }
      transition={{
        duration: shaking ? 0.45 : bursting ? 0.6 : 0.4,
        type: shaking || bursting ? 'keyframes' : 'spring',
        stiffness: 260, damping: 20,
      }}
      style={{
        aspectRatio: '3 / 4',
        padding: 0,
        border: 'none',
        cursor: flipped ? 'default' : 'pointer',
        background: 'transparent',
        position: 'relative',
        transformStyle: 'preserve-3d',
        perspective: 700,
        minHeight: 72,
      }}
    >
      {/* ── BACK: rune-stamped velvet tile with candle flicker ── */}
      <div
        className="arcade-rune-back"
        style={{
          position: 'absolute', inset: 0,
          borderRadius: 12,
          background: `
            radial-gradient(circle at 50% 30%, rgba(245,197,66,0.12), transparent 60%),
            linear-gradient(160deg, #2A1B4E 0%, #15102A 70%, #0B0818 100%)`,
          border: '1.5px solid color-mix(in srgb, var(--arcade-accent, #8338EC) 55%, transparent)',
          boxShadow: `
            inset 0 0 14px rgba(131,56,236,0.25),
            inset 0 2px 0 rgba(255,255,255,0.06),
            0 4px 14px rgba(0,0,0,0.5)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backfaceVisibility: 'hidden',
        }}
      >
        <span
          className="mm-rune"
          style={{ fontSize: 'clamp(24px, 6vw, 44px)' }}
        >
          {card.rune}
        </span>
      </div>

      {/* ── FRONT: glyph + text panel ── */}
      <div
        style={{
          position: 'absolute', inset: 0,
          padding: 8,
          borderRadius: 12,
          background: matched
            ? 'linear-gradient(180deg, #F5C542 0%, #B9851D 100%)'
            : card.type === 'Q'
              ? 'linear-gradient(180deg, #E8DCFF 0%, #B39CE8 100%)'
              : 'linear-gradient(180deg, #CDE1FF 0%, #8CA7D6 100%)',
          color: '#1A0D26',
          border: matched
            ? '2px solid #FFE48A'
            : '1.5px solid rgba(255,255,255,0.7)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          textAlign: 'center',
          transform: 'rotateY(180deg)',
          backfaceVisibility: 'hidden',
          fontFamily: 'Space Grotesk, sans-serif',
          fontWeight: 700,
          fontSize: 'clamp(10px, 1.3vw, 13px)',
          lineHeight: 1.2,
          overflow: 'hidden',
          boxShadow: matched
            ? '0 0 24px rgba(245,197,66,0.8), inset 0 0 12px rgba(255,255,255,0.4)'
            : 'inset 0 0 8px rgba(0,0,0,0.15)',
        }}
      >
        {/* Mini rune in corner: teaches the pair glyph so runes carry meaning */}
        <span
          style={{
            position: 'absolute', top: 4, right: 6,
            fontFamily: "'DM Serif Display', serif",
            fontSize: 12,
            color: matched ? '#6B3F00' : 'rgba(26,13,38,0.4)',
          }}
        >
          {card.rune}
        </span>
        <span
          style={{
            position: 'absolute', top: 4, left: 6,
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 7, letterSpacing: 1,
            color: matched ? '#6B3F00' : 'rgba(26,13,38,0.55)',
          }}
        >
          {card.type}
        </span>
        <span style={{ padding: '8px 4px 4px', wordBreak: 'break-word' }}>{card.text}</span>
        {matched && (
          <Sparkles
            style={{
              position: 'absolute', bottom: 4, right: 4,
              width: 14, height: 14, color: '#6B3F00',
            }}
          />
        )}
      </div>

    </motion.button>
  );
}

// ============================================================
//             StageHudBand — mirrors CabinetStage HUD
// ============================================================
// Kept inline so the shell renders its own HUD-like strip even when the
// parent page forgets to pass hudLeft/hudRight up to CabinetStage.

function StageHudBand({ left, right }) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px',
        borderRadius: 12,
        background: 'linear-gradient(180deg, rgba(10,10,24,0.85), rgba(10,10,24,0.6))',
        border: '1px solid rgba(255,255,255,0.08)',
        marginBottom: 14,
        gap: 12, flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>{left}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>{right}</div>
    </div>
  );
}

// ============================================================
//               TeacherProgress — live matches per student
// ============================================================

function TeacherProgress({ players, totalPairs }) {
  // Players array comes from the live game socket. Each player's `score` is
  // bumped by the MCQ channel — for MemoryMatch, each correct emit is one match,
  // so answers_correct ≈ matches. Fall back to deriving from score (~100pts/match,
  // inexact because of the streak multiplier but good enough to drive the bar).
  const playersKey = (players || []).map(p => (p.player_id || p.id) + ':' + (p.score || 0)).join('|');

  // Client-side completion ledger: when a player first hits total pairs, stamp
  // the moment. Gives us "finished order" + relative timestamps for medals.
  const [completionTimes, setCompletionTimes] = useState({}); // { playerId: epochMs }
  const [fanfareFired, setFanfareFired] = useState(false);
  const firstFinishRef = useRef(null);

  const rows = useMemo(() => {
    return (players || []).map(p => {
      const rawMatches = p.memory_matches ?? p.answers_correct ?? Math.round((p.score || 0) / 100);
      const clamped = Math.max(0, Math.min(rawMatches, totalPairs));
      return {
        id: p.player_id || p.id,
        name: p.name || p.display_name || 'Player',
        avatar: p.avatar || '🎭',
        matches: clamped,
        score: p.score || 0,
        done: clamped >= totalPairs,
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playersKey, totalPairs]);

  // Record completion timestamps as players cross the finish line.
  useEffect(() => {
    setCompletionTimes(prev => {
      const next = { ...prev };
      let changed = false;
      rows.forEach(r => {
        if (r.done && !next[r.id]) {
          next[r.id] = Date.now();
          if (!firstFinishRef.current) firstFinishRef.current = next[r.id];
          changed = true;
        }
      });
      return changed ? next : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows.map(r => r.id + ':' + r.done).join('|')]);

  // Fanfare + confetti when the LAST active player finishes.
  useEffect(() => {
    if (fanfareFired) return;
    if (rows.length === 0) return;
    const allDone = rows.every(r => r.done);
    if (allDone) {
      setFanfareFired(true);
      play('fanfare');
      winnerCelebration();
    }
  }, [rows, fanfareFired]);

  // Build ranked list: finished players in completion order (medals),
  // then unfinished sorted by progress.
  const ranked = useMemo(() => {
    const finished = rows
      .filter(r => r.done)
      .map(r => ({ ...r, finishedAt: completionTimes[r.id] || 0 }))
      .sort((a, b) => a.finishedAt - b.finishedAt);
    const unfinished = rows
      .filter(r => !r.done)
      .sort((a, b) => b.matches - a.matches || b.score - a.score);
    return [...finished, ...unfinished];
  }, [rows, completionTimes]);

  const firstFinishAt = firstFinishRef.current;
  const finishedCount = ranked.filter(r => r.done).length;

  return (
    <div
      style={{
        maxWidth: 960, margin: '22px auto 0',
        padding: '16px 18px',
        borderRadius: 14,
        background: 'linear-gradient(180deg, rgba(10,10,24,0.75), rgba(10,10,24,0.55))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 10, gap: 12, flexWrap: 'wrap',
        }}
      >
        <div
          style={{
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 10, letterSpacing: 2,
            color: 'var(--arcade-accent, #8338EC)',
          }}
        >
          LIVE · {ranked.length} PLAYER{ranked.length === 1 ? '' : 'S'}
        </div>
        {finishedCount > 0 && (
          <div
            style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 9, letterSpacing: 1.5,
              color: '#F5C542',
              padding: '4px 10px', borderRadius: 999,
              background: 'rgba(245,197,66,0.12)',
              border: '1px solid rgba(245,197,66,0.35)',
            }}
          >
            {finishedCount}/{ranked.length} FINISHED
          </div>
        )}
      </div>
      {ranked.length === 0 ? (
        <div style={{ fontSize: 13, color: 'rgba(247,247,255,0.55)' }}>
          Waiting for students to start flipping tiles…
        </div>
      ) : (
        <motion.div
          layout
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))',
            gap: 10,
          }}
        >
          {ranked.map((r, idx) => {
            const pct = totalPairs > 0 ? (r.matches / totalPairs) * 100 : 0;
            const finishRank = r.done ? idx + 1 : null; // 1-based
            const medal = finishRank === 1 ? '🥇' : finishRank === 2 ? '🥈' : finishRank === 3 ? '🥉' : null;
            const deltaMs = r.done && firstFinishAt ? Math.max(0, r.finishedAt - firstFinishAt) : 0;
            const deltaLabel = finishRank === 1 ? 'FIRST!' : `+${Math.round(deltaMs / 1000)}s`;
            return (
              <motion.div
                layout
                key={r.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', stiffness: 260, damping: 22 }}
                style={{
                  padding: '10px 12px',
                  borderRadius: 10,
                  background: r.done
                    ? 'linear-gradient(180deg, rgba(245,197,66,0.22), rgba(10,10,24,0.7))'
                    : 'rgba(10,10,24,0.6)',
                  border: `1px solid ${r.done ? 'rgba(245,197,66,0.55)' : 'rgba(255,255,255,0.08)'}`,
                  boxShadow: finishRank === 1 ? '0 0 18px rgba(245,197,66,0.35)' : 'none',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginBottom: 6, gap: 8,
                  }}
                >
                  <span
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      fontFamily: 'Space Grotesk, sans-serif',
                      fontSize: 13, fontWeight: 700,
                      color: r.done ? '#F5C542' : 'rgba(247,247,255,0.85)',
                      minWidth: 0,
                    }}
                  >
                    {medal && <span style={{ fontSize: 16 }}>{medal}</span>}
                    <span style={{ fontSize: 15 }}>{r.avatar}</span>
                    <span style={{
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>{r.name}</span>
                  </span>
                  <span
                    style={{
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 9, letterSpacing: 1.5,
                      color: r.done ? '#F5C542' : 'rgba(247,247,255,0.7)',
                      flexShrink: 0,
                    }}
                  >
                    {r.done ? deltaLabel : `${r.matches}/${totalPairs}`}
                  </span>
                </div>
                <div
                  style={{
                    height: 6, borderRadius: 999,
                    background: 'rgba(255,255,255,0.08)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${pct}%`,
                      height: '100%',
                      background: r.done
                        ? 'linear-gradient(90deg, #F5C542, #FFDE7A)'
                        : 'linear-gradient(90deg, var(--arcade-accent, #8338EC), #C77DFF)',
                      transition: 'width 0.35s ease',
                      boxShadow: r.done
                        ? '0 0 10px rgba(245,197,66,0.6)'
                        : '0 0 8px rgba(131,56,236,0.5)',
                    }}
                  />
                </div>
              </motion.div>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}

// ============================================================
//         WaitingOnClassmates — student early-finisher strip
// ============================================================

function WaitingOnClassmates({ players, totalPairs, selfId }) {
  const others = useMemo(() => {
    return (players || [])
      .filter(p => (p.player_id || p.id) !== selfId)
      .map(p => {
        const rawMatches = p.memory_matches ?? p.answers_correct ?? Math.round((p.score || 0) / 100);
        const matches = Math.max(0, Math.min(rawMatches, totalPairs));
        return {
          id: p.player_id || p.id,
          name: p.name || 'Player',
          avatar: p.avatar || '🎭',
          matches,
          done: matches >= totalPairs,
        };
      });
  }, [players, totalPairs, selfId]);

  if (others.length === 0) return null;

  const remaining = others.filter(o => !o.done).length;
  const allOthersDone = remaining === 0;

  return (
    <div
      style={{
        maxWidth: 620, margin: '18px auto 0',
        padding: '14px 18px',
        borderRadius: 14,
        background: 'linear-gradient(180deg, rgba(10,10,24,0.7), rgba(10,10,24,0.5))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div
        style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2,
          color: allOthersDone ? '#F5C542' : 'rgba(247,247,255,0.65)',
          marginBottom: 10,
          textAlign: 'center',
        }}
      >
        {allOthersDone
          ? '★ EVERYONE FINISHED ★'
          : `WAITING ON ${remaining} CLASSMATE${remaining === 1 ? '' : 'S'}…`}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {others
          .slice()
          .sort((a, b) => (b.matches - a.matches))
          .map(o => {
            const pct = totalPairs > 0 ? (o.matches / totalPairs) * 100 : 0;
            return (
              <div
                key={o.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '6px 10px', borderRadius: 8,
                  background: o.done ? 'rgba(245,197,66,0.1)' : 'rgba(255,255,255,0.04)',
                }}
              >
                <span style={{ fontSize: 14 }}>{o.avatar}</span>
                <span style={{
                  flex: 1, minWidth: 0,
                  fontFamily: 'Space Grotesk, sans-serif',
                  fontSize: 12, fontWeight: 600,
                  color: o.done ? '#F5C542' : 'rgba(247,247,255,0.8)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {o.name}
                </span>
                <div
                  style={{
                    flex: '0 0 120px',
                    height: 5, borderRadius: 999,
                    background: 'rgba(255,255,255,0.08)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${pct}%`, height: '100%',
                      background: o.done
                        ? 'linear-gradient(90deg, #F5C542, #FFDE7A)'
                        : 'linear-gradient(90deg, var(--arcade-accent, #8338EC), #C77DFF)',
                      transition: 'width 0.35s ease',
                    }}
                  />
                </div>
                <span style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 8, letterSpacing: 1,
                  color: o.done ? '#F5C542' : 'rgba(247,247,255,0.55)',
                  minWidth: 34, textAlign: 'right',
                }}>
                  {o.done ? 'DONE' : `${o.matches}/${totalPairs}`}
                </span>
              </div>
            );
          })}
      </div>
    </div>
  );
}

// ============================================================
//                        WinStat helper
// ============================================================

function WinStat({ label, value }) {
  return (
    <div
      style={{
        padding: '8px 14px',
        borderRadius: 10,
        background: 'rgba(10,10,24,0.6)',
        border: '1px solid rgba(255,255,255,0.1)',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 8, letterSpacing: 1.5, color: 'rgba(247,247,255,0.5)',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 14,
          color: '#F5C542',
        }}
      >
        {value}
      </div>
    </div>
  );
}

// ============================================================
//              seededShuffle — deterministic per player
// ============================================================

function seededShuffle(arr, seed) {
  let h = 2166136261;
  const s = String(seed || 'anon');
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
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
