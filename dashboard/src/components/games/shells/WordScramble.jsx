'use client';
import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shuffle, ArrowDownCircle, Trash2, CheckCircle, Trophy, Clock } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer, winnerCelebration } from '@/lib/confetti';
import { ArcadeChip } from '@/components/games/CabinetStage';
import { buildTrie, loadDictionary, getDictionary } from '@/lib/wordTrie';

/**
 * Word Scramble — arcade-cabinet edition (v1 April 2026). FINAL SHELL.
 *
 * Warm yellow #FFE14F accent from registry. Wooden game table interior.
 * Students drag letter tiles from a rack onto a 15×15 crossword grid and
 * build interlocking words. All word validation is client-side via a
 * SOWPODS trie (~267K words).
 *
 * Renders inside CabinetStage. Interior content only — no full-page bg.
 *
 * Game flow (timed solo rounds):
 *   1. Each student gets an initial pool of tiles (seeded from config).
 *   2. Timer counts down (config.round_length_minutes, default 10).
 *   3. At draw intervals (peel_interval_seconds), new tiles are added to everyone's rack.
 *   4. Students build valid crossword patterns on their grid.
 *   5. At buzzer: score = valid tiles (+1 each, +2 curriculum bonus)
 *      minus unused tiles in rack (-1 each).
 *
 * Actions:
 *   - DUMP: swap 1 tile for 3 random from reserve (costs net +2 tiles)
 *   - SHUFFLE: rearrange rack tiles randomly (IEP accommodation)
 *
 * Server contract:
 *   - This shell is timer-driven, not question-driven.
 *   - onAnswer(JSON.stringify({ grid, words, score })) fires at game end.
 *   - allQuestions is ignored; config carries game settings.
 *
 * Props: allQuestions, question, players, view, onAnswer, config,
 *        questionIndex, totalQuestions, lastResult, playerId
 */

// ── Standard letter distribution (144 tiles) ──
const LETTER_DIST = {
  A:13,B:3,C:3,D:6,E:18,F:3,G:4,H:3,I:12,J:2,K:2,L:5,M:3,
  N:8,O:11,P:3,Q:2,R:9,S:6,T:9,U:6,V:3,W:3,X:2,Y:3,Z:2,
};
const LETTER_POINTS = {
  A:1,B:3,C:3,D:2,E:1,F:4,G:2,H:4,I:1,J:8,K:5,L:1,M:3,
  N:1,O:1,P:3,Q:10,R:1,S:1,T:1,U:1,V:4,W:4,X:8,Y:4,Z:10,
};

const GRID_SIZE = 15;
const INITIAL_TILES = 21; // starting hand for 2+ players
const DRAW_TILES = 1;     // tiles gained per draw round

// Seeded RNG (FNV-1a)
function seededRng(seed) {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h ^= h << 13; h ^= h >> 17; h ^= h << 5;
    return ((h >>> 0) / 4294967296);
  };
}

function buildPool(seed) {
  const rng = seededRng(seed || 'default');
  const pool = [];
  for (const [letter, count] of Object.entries(LETTER_DIST)) {
    for (let i = 0; i < count; i++) pool.push(letter);
  }
  // Fisher-Yates shuffle
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool;
}

// Extract all words from grid (rows and columns, min length 2)
function extractWords(grid) {
  const words = [];
  const size = grid.length;

  // Rows
  for (let r = 0; r < size; r++) {
    let word = '', startC = -1;
    for (let c = 0; c <= size; c++) {
      const ch = c < size ? grid[r][c] : null;
      if (ch) {
        if (word.length === 0) startC = c;
        word += ch;
      } else {
        if (word.length >= 2) words.push({ text: word, dir: 'row', r, c: startC, len: word.length });
        word = '';
      }
    }
  }
  // Columns
  for (let c = 0; c < size; c++) {
    let word = '', startR = -1;
    for (let r = 0; r <= size; r++) {
      const ch = r < size ? grid[r][c] : null;
      if (ch) {
        if (word.length === 0) startR = r;
        word += ch;
      } else {
        if (word.length >= 2) words.push({ text: word, dir: 'col', r: startR, c, len: word.length });
        word = '';
      }
    }
  }
  return words;
}

// Check all tiles are connected (flood fill from first tile)
function isConnected(grid) {
  const size = grid.length;
  let firstR = -1, firstC = -1, total = 0;
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (grid[r][c]) {
        total++;
        if (firstR === -1) { firstR = r; firstC = c; }
      }
    }
  }
  if (total <= 1) return total === 1;

  const visited = new Set();
  const queue = [[firstR, firstC]];
  visited.add(`${firstR},${firstC}`);
  while (queue.length) {
    const [r, c] = queue.shift();
    for (const [dr, dc] of [[0,1],[0,-1],[1,0],[-1,0]]) {
      const nr = r + dr, nc = c + dc;
      const key = `${nr},${nc}`;
      if (nr >= 0 && nr < size && nc >= 0 && nc < size && grid[nr][nc] && !visited.has(key)) {
        visited.add(key);
        queue.push([nr, nc]);
      }
    }
  }
  return visited.size === total;
}

// Score the grid
function scoreGrid(grid, dict, curriculumWords = []) {
  const words = extractWords(grid);
  const currSet = new Set(curriculumWords.map(w => w.toUpperCase()));
  let validTiles = 0, invalidCount = 0, bonusTiles = 0;
  const validWords = [], invalidWords = [];

  for (const w of words) {
    if (dict && dict.isWord(w.text)) {
      validWords.push(w);
      // Count tiles (avoid double-counting intersections — we'll handle below)
      const isCurriculum = currSet.has(w.text);
      if (isCurriculum) bonusTiles += w.len;
    } else {
      invalidWords.push(w);
      invalidCount++;
    }
  }

  // Count total placed tiles
  let placedCount = 0;
  for (let r = 0; r < grid.length; r++) {
    for (let c = 0; c < grid[r].length; c++) {
      if (grid[r][c]) placedCount++;
    }
  }

  const connected = isConnected(grid);
  const allValid = invalidCount === 0;
  // Score: +1 per valid placed tile, +1 bonus per curriculum tile, -penalty for invalid
  const score = allValid && connected
    ? placedCount + bonusTiles
    : Math.max(0, placedCount - invalidCount * 3);

  return { score, validWords, invalidWords, placedCount, connected, allValid, bonusTiles };
}

// ══════════════════════════════════════════════════════
//                    MAIN COMPONENT
// ══════════════════════════════════════════════════════

export default function WordScramble({
  allQuestions = [], question, players = [], view = 'student',
  onAnswer, config = {},
  questionIndex = 0, totalQuestions = 0, lastResult = null, playerId = null,
}) {
  const roundMinutes = config.round_length_minutes || 10;
  const peelInterval = config.peel_interval_seconds || 60;
  const useCurriculumBonus = config.use_curriculum_bonus !== false;
  const curriculumWords = useMemo(() => config.curriculum_words || [], [config.curriculum_words]);

  // ── Grid state ──
  const [grid, setGrid] = useState(() =>
    Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill(null))
  );
  const [rack, setRack] = useState([]);
  const [reserve, setReserve] = useState([]);
  const [dragging, setDragging] = useState(null); // { letter, source: 'rack'|'grid', rackIdx?, gridR?, gridC? }
  const [hoverCell, setHoverCell] = useState(null);
  const [dictReady, setDictReady] = useState(false);
  const [timeLeft, setTimeLeft] = useState(roundMinutes * 60);
  const [gameStarted, setGameStarted] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [finalScore, setFinalScore] = useState(null);
  const [drawCount, setDrawCount] = useState(0);
  const [validationResult, setValidationResult] = useState(null);
  const [showValidation, setShowValidation] = useState(false);
  const timerRef = useRef(null);
  const drawTimerRef = useRef(null);
  const gridRef = useRef(grid);
  gridRef.current = grid;

  // ── Load dictionary ──
  useEffect(() => {
    loadDictionary().then(() => setDictReady(true));
  }, []);

  // ── Initialize tile pool ──
  useEffect(() => {
    const pool = buildPool(playerId || 'student');
    const hand = pool.splice(0, INITIAL_TILES);
    setRack(hand);
    setReserve(pool);
    setGameStarted(true);
  }, [playerId]);

  // ── Timer ──
  useEffect(() => {
    if (!gameStarted || gameOver || view !== 'student') return;
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) {
          clearInterval(timerRef.current);
          endGame();
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [gameStarted, gameOver, view]);

  // ── Draw timer ──
  useEffect(() => {
    if (!gameStarted || gameOver || view !== 'student' || peelInterval <= 0) return;
    drawTimerRef.current = setInterval(() => {
      doDraw();
    }, peelInterval * 1000);
    return () => clearInterval(drawTimerRef.current);
  }, [gameStarted, gameOver, view, peelInterval]);

  // ── Draw: add tiles to rack from reserve ──
  const doDraw = useCallback(() => {
    setReserve(prev => {
      if (prev.length === 0) return prev;
      const newTiles = prev.slice(0, DRAW_TILES);
      const rest = prev.slice(DRAW_TILES);
      setRack(r => [...r, ...newTiles]);
      setDrawCount(p => p + 1);
      play('tick');
      return rest;
    });
  }, []);

  // ── Dump: swap 1 rack tile for 3 from reserve ──
  const doDump = useCallback((rackIdx) => {
    setReserve(prev => {
      if (prev.length < 3) return prev; // not enough tiles
      const drawn = prev.slice(0, 3);
      const rest = prev.slice(3);
      setRack(r => {
        const dumped = r[rackIdx];
        const next = [...r];
        next.splice(rackIdx, 1, ...drawn);
        // Put dumped tile back at end of reserve
        rest.push(dumped);
        return next;
      });
      play('whoosh');
      return rest;
    });
  }, []);

  // ── Shuffle rack ──
  const shuffleRack = useCallback(() => {
    setRack(r => {
      const next = [...r];
      for (let i = next.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [next[i], next[j]] = [next[j], next[i]];
      }
      return next;
    });
    play('whoosh');
  }, []);

  // ── End game ──
  const endGame = useCallback(() => {
    if (gameOver) return;
    setGameOver(true);
    clearInterval(timerRef.current);
    clearInterval(drawTimerRef.current);

    const dict = getDictionary();
    const result = scoreGrid(gridRef.current, dict, curriculumWords);
    const unusedPenalty = rack.length;
    const total = Math.max(0, result.score - unusedPenalty);

    setFinalScore({ ...result, unusedPenalty, total });

    if (result.allValid && result.connected && result.placedCount > 0) {
      play('fanfare');
      winnerCelebration();
    } else {
      play('correct');
      correctAnswer({ x: 0.5, y: 0.45 });
    }

    // Report to server
    onAnswer?.(JSON.stringify({
      grid: gridRef.current,
      words: result.validWords.map(w => w.text),
      score: total,
      placed: result.placedCount,
      unused: rack.length,
    }));
  }, [gameOver, rack, curriculumWords, onAnswer]);

  // ── Validate current board (preview) ──
  const validateBoard = useCallback(() => {
    const dict = getDictionary();
    if (!dict) return;
    const result = scoreGrid(grid, dict, curriculumWords);
    setValidationResult(result);
    setShowValidation(true);
    setTimeout(() => setShowValidation(false), 3000);
  }, [grid, curriculumWords]);

  // ── Drag & drop handlers ──
  const startDragFromRack = (letter, idx) => {
    setDragging({ letter, source: 'rack', rackIdx: idx });
  };

  const startDragFromGrid = (r, c) => {
    const letter = grid[r][c];
    if (!letter) return;
    setDragging({ letter, source: 'grid', gridR: r, gridC: c });
    // Remove from grid immediately for visual feedback
    setGrid(g => {
      const next = g.map(row => [...row]);
      next[r][c] = null;
      return next;
    });
  };

  const dropOnCell = useCallback((r, c) => {
    if (!dragging) return;
    if (grid[r][c]) {
      // Cell occupied — swap if from grid, or return to rack
      if (dragging.source === 'grid') {
        // Put dragged tile here, move existing tile back to where dragged came from
        const existing = grid[r][c];
        setGrid(g => {
          const next = g.map(row => [...row]);
          next[r][c] = dragging.letter;
          next[dragging.gridR][dragging.gridC] = existing;
          return next;
        });
      } else {
        // Return to rack
        play('incorrect');
        return;
      }
    } else {
      // Empty cell — place tile
      setGrid(g => {
        const next = g.map(row => [...row]);
        next[r][c] = dragging.letter;
        return next;
      });
    }

    // Remove from source
    if (dragging.source === 'rack') {
      setRack(r => {
        const next = [...r];
        next.splice(dragging.rackIdx, 1);
        return next;
      });
    }
    // grid source already removed in startDragFromGrid

    play('tick');
    setDragging(null);
    setHoverCell(null);
  }, [dragging, grid]);

  const dropOnRack = useCallback(() => {
    if (!dragging) return;
    if (dragging.source === 'grid') {
      // Return grid tile to rack
      setRack(r => [...r, dragging.letter]);
    }
    // If from rack, it's a no-op (already in rack)
    setDragging(null);
    setHoverCell(null);
  }, [dragging]);

  const cancelDrag = useCallback(() => {
    if (!dragging) return;
    if (dragging.source === 'grid') {
      // Put tile back
      setGrid(g => {
        const next = g.map(row => [...row]);
        next[dragging.gridR][dragging.gridC] = dragging.letter;
        return next;
      });
    }
    setDragging(null);
    setHoverCell(null);
  }, [dragging]);

  // Format time
  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const timeStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;
  const isUrgent = timeLeft <= 30;

  // Count placed tiles
  const placedCount = useMemo(() => {
    let c = 0;
    for (const row of grid) for (const cell of row) if (cell) c++;
    return c;
  }, [grid]);

  // ── HUD ──
  const hudLeft = (
    <>
      <ArcadeChip>{rack.length} IN RACK</ArcadeChip>
      <ArcadeChip variant="ghost">{placedCount} PLACED</ArcadeChip>
    </>
  );
  const hudRight = (
    <>
      <ArcadeChip variant="ghost">DRAW {drawCount}</ArcadeChip>
      <ArcadeChip variant={isUrgent ? 'solid' : 'ghost'}>
        <Clock style={{ width: 12, height: 12 }} /> {timeStr}
      </ArcadeChip>
    </>
  );

  // ══════════════════════════════════════════════════
  //                    GAME OVER
  // ══════════════════════════════════════════════════
  if (gameOver && finalScore && view === 'student') {
    return (
      <div style={{ padding: '4px 0 24px', color: 'var(--arcade-ink, #F7F7FF)' }}>
        <StageHudBand left={hudLeft} right={<ArcadeChip>TIME'S UP</ArcadeChip>} />
        <motion.div
          initial={{ opacity: 0, scale: 0.85, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 220, damping: 18 }}
          style={{
            maxWidth: 640, margin: '40px auto',
            padding: '36px 28px', textAlign: 'center',
            background: 'linear-gradient(180deg, rgba(255,225,79,0.15), rgba(10,10,24,0.85))',
            border: '2px solid var(--arcade-accent, #FFE14F)',
            borderRadius: 18,
            boxShadow: '0 0 40px color-mix(in srgb, var(--arcade-accent, #FFE14F) 35%, transparent)',
          }}
        >
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 12,
            letterSpacing: 2.5, color: 'var(--arcade-accent, #FFE14F)', marginBottom: 12,
          }}>
            {finalScore.allValid && finalScore.connected ? '★ BANANA SPLIT ★' : '★ TIME\'S UP ★'}
          </div>
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 26,
            letterSpacing: 2, color: '#FFE14F', marginBottom: 16,
            textShadow: '0 0 18px rgba(255,225,79,0.6)',
          }}>
            {finalScore.total} PTS
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
            <WinStat label="PLACED" value={finalScore.placedCount} accent="#FFE14F" />
            <WinStat label="WORDS" value={finalScore.validWords.length} accent="#FFE14F" />
            <WinStat label="INVALID" value={finalScore.invalidWords.length} accent={finalScore.invalidWords.length > 0 ? '#FF3864' : '#FFE14F'} />
            <WinStat label="UNUSED" value={`-${finalScore.unusedPenalty}`} accent="#FF8A6E" />
            {finalScore.bonusTiles > 0 && (
              <WinStat label="BONUS" value={`+${finalScore.bonusTiles}`} accent="#16D474" />
            )}
          </div>
          {finalScore.validWords.length > 0 && (
            <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
              {finalScore.validWords.map((w, i) => (
                <span key={i} style={{
                  padding: '4px 8px', borderRadius: 6,
                  background: 'rgba(255,225,79,0.15)',
                  border: '1px solid rgba(255,225,79,0.3)',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 8, letterSpacing: 1, color: '#FFE14F',
                }}>
                  {w.text}
                </span>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    );
  }

  // ══════════════════════════════════════════════════
  //                  STUDENT VIEW
  // ══════════════════════════════════════════════════
  if (view === 'student') {
    return (
      <div style={{ padding: '4px 0 24px', color: 'var(--arcade-ink, #F7F7FF)' }}
        onMouseUp={cancelDrag} onTouchEnd={cancelDrag}
      >
        <StageHudBand left={hudLeft} right={hudRight} />

        {/* Validation toast */}
        <AnimatePresence>
          {showValidation && validationResult && (
            <motion.div
              initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              style={{
                textAlign: 'center', marginBottom: 8,
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 10, letterSpacing: 2,
                color: validationResult.allValid && validationResult.connected ? '#16D474' : '#FF3864',
              }}
            >
              {validationResult.allValid && validationResult.connected
                ? `✓ ${validationResult.validWords.length} VALID WORDS · ALL CONNECTED`
                : validationResult.invalidWords.length > 0
                  ? `✗ ${validationResult.invalidWords.length} INVALID: ${validationResult.invalidWords.map(w => w.text).join(', ')}`
                  : '✗ TILES NOT CONNECTED'}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Grid */}
        <div style={{
          maxWidth: 520, margin: '0 auto 12px',
          padding: 8, borderRadius: 14,
          background: `
            radial-gradient(circle at 50% 50%, rgba(255,225,79,0.06), transparent 60%),
            linear-gradient(180deg, #1A1510, #0F0D08)`,
          border: '2px solid color-mix(in srgb, var(--arcade-accent, #FFE14F) 40%, transparent)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${GRID_SIZE}, 1fr)`,
            gap: 1,
            aspectRatio: '1',
          }}>
            {grid.map((row, r) =>
              row.map((cell, c) => (
                <div
                  key={`${r}-${c}`}
                  onMouseUp={() => dropOnCell(r, c)}
                  onTouchEnd={(e) => { e.preventDefault(); dropOnCell(r, c); }}
                  onMouseEnter={() => dragging && setHoverCell({ r, c })}
                  onMouseDown={() => cell && startDragFromGrid(r, c)}
                  onTouchStart={() => cell && startDragFromGrid(r, c)}
                  style={{
                    width: '100%', aspectRatio: '1',
                    borderRadius: 3,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 'clamp(8px, 2.2vw, 14px)',
                    fontFamily: "'Press Start 2P', monospace",
                    fontWeight: 700,
                    cursor: cell ? 'grab' : dragging ? 'crosshair' : 'default',
                    background: cell
                      ? 'linear-gradient(180deg, #F5E6B8, #D4B876)'
                      : hoverCell?.r === r && hoverCell?.c === c
                        ? 'rgba(255,225,79,0.15)'
                        : 'rgba(255,255,255,0.03)',
                    color: cell ? '#2A1F08' : 'transparent',
                    border: hoverCell?.r === r && hoverCell?.c === c
                      ? '1px solid rgba(255,225,79,0.5)'
                      : '1px solid rgba(255,255,255,0.05)',
                    boxShadow: cell ? '0 2px 4px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.3)' : 'none',
                    transition: 'background 0.1s, border 0.1s',
                    userSelect: 'none',
                  }}
                >
                  {cell || ''}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div style={{
          display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 10,
        }}>
          <ActionBtn icon={<Shuffle style={{ width: 14, height: 14 }} />} label="SHUFFLE" onClick={shuffleRack} />
          <ActionBtn icon={<CheckCircle style={{ width: 14, height: 14 }} />} label="CHECK" onClick={validateBoard} accent="#16D474" />
        </div>

        {/* Tile rack */}
        <div
          onMouseUp={dropOnRack}
          onTouchEnd={(e) => { e.preventDefault(); dropOnRack(); }}
          style={{
            maxWidth: 600, margin: '0 auto',
            padding: '10px 12px',
            borderRadius: 12,
            background: 'linear-gradient(180deg, rgba(42,31,8,0.8), rgba(15,13,8,0.9))',
            border: '2px solid color-mix(in srgb, var(--arcade-accent, #FFE14F) 30%, transparent)',
            minHeight: 60,
          }}
        >
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 5, justifyContent: 'center',
          }}>
            {rack.map((letter, i) => (
              <motion.div
                key={`rack-${i}-${letter}`}
                layout
                whileHover={{ scale: 1.08, y: -2 }}
                whileTap={{ scale: 0.95 }}
                onMouseDown={() => startDragFromRack(letter, i)}
                onTouchStart={() => startDragFromRack(letter, i)}
                style={{
                  width: 36, height: 40,
                  borderRadius: 5,
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  background: 'linear-gradient(180deg, #F5E6B8, #D4B876)',
                  color: '#2A1F08',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 14, fontWeight: 700,
                  cursor: 'grab',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.4)',
                  position: 'relative',
                  userSelect: 'none',
                }}
              >
                {letter}
                <span style={{
                  position: 'absolute', bottom: 2, right: 3,
                  fontSize: 6, color: 'rgba(42,31,8,0.5)',
                }}>
                  {LETTER_POINTS[letter]}
                </span>
                {/* Dump button on long press / right side */}
                <button
                  onClick={(e) => { e.stopPropagation(); doDump(i); }}
                  onTouchEnd={(e) => { e.stopPropagation(); e.preventDefault(); doDump(i); }}
                  title="Dump: swap for 3 tiles"
                  style={{
                    position: 'absolute', top: -6, right: -6,
                    width: 14, height: 14, borderRadius: '50%',
                    background: '#FF3864', border: 'none', color: '#fff',
                    fontSize: 8, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    opacity: 0, transition: 'opacity 0.15s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                  onMouseLeave={(e) => e.currentTarget.style.opacity = '0'}
                >
                  ×
                </button>
              </motion.div>
            ))}
            {rack.length === 0 && (
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 9, color: 'rgba(255,225,79,0.4)', padding: 10,
              }}>
                RACK EMPTY — ALL TILES PLACED
              </div>
            )}
          </div>
        </div>

        {/* Reserve info */}
        <div style={{
          textAlign: 'center', marginTop: 10,
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 8, letterSpacing: 1.5,
          color: 'rgba(247,247,255,0.4)',
        }}>
          {reserve.length} TILES IN RESERVE · NEXT DRAW IN {peelInterval}s
        </div>

        {!dictReady && (
          <div style={{
            textAlign: 'center', marginTop: 8,
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 8, color: 'rgba(255,225,79,0.5)',
          }}>
            LOADING DICTIONARY...
          </div>
        )}
      </div>
    );
  }

  // ══════════════════════════════════════════════════
  //                  TEACHER VIEW
  // ══════════════════════════════════════════════════
  return (
    <div style={{ padding: '4px 0 24px', color: 'var(--arcade-ink, #F7F7FF)' }}>
      <StageHudBand left={hudLeft} right={hudRight} />
      <TeacherWall players={players} timeStr={timeStr} drawCount={drawCount} />
    </div>
  );
}

// ══════════════════════════════════════════════════════
//              Teacher Wall-of-Grids
// ══════════════════════════════════════════════════════

function TeacherWall({ players, timeStr, drawCount }) {
  const rows = useMemo(() => {
    return (players || []).map(p => ({
      id: p.player_id || p.id,
      name: p.name || p.display_name || 'Player',
      score: p.score || 0,
      words: p.words_found ?? 0,
      placed: p.tiles_placed ?? 0,
    })).sort((a, b) => b.score - a.score);
  }, [players]);

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* Game status */}
      <div style={{
        padding: '20px 24px', marginBottom: 16,
        borderRadius: 14, textAlign: 'center',
        background: `radial-gradient(circle at 50% 0%, rgba(255,225,79,0.12), transparent 55%),
          linear-gradient(180deg, #1A1510, #0F0D08)`,
        border: '2px solid var(--arcade-accent, #FFE14F)',
        boxShadow: '0 0 24px rgba(255,225,79,0.2)',
      }}>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 24, color: '#FFE14F',
          textShadow: '0 0 18px rgba(255,225,79,0.4)',
          marginBottom: 8,
        }}>
          {timeStr}
        </div>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2,
          color: 'var(--arcade-ink-dim, #B6B7D8)',
        }}>
          DRAW {drawCount} · {rows.length} PLAYER{rows.length !== 1 ? 'S' : ''}
        </div>
      </div>

      {/* Leaderboard */}
      <div style={{
        padding: '16px 18px', borderRadius: 14,
        background: 'linear-gradient(180deg, rgba(10,10,24,0.75), rgba(10,10,24,0.55))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2, color: 'var(--arcade-accent, #FFE14F)', marginBottom: 12,
        }}>
          WORD BUILDERS · {rows.length} PLAYER{rows.length !== 1 ? 'S' : ''}
        </div>
        {rows.length === 0 ? (
          <div style={{ fontSize: 13, color: 'rgba(247,247,255,0.55)' }}>
            Waiting for players to join…
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rows.map((r, idx) => (
              <div key={r.id} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 14px', borderRadius: 10,
                background: idx === 0
                  ? 'linear-gradient(90deg, rgba(255,225,79,0.12), rgba(10,10,24,0.7))'
                  : 'rgba(10,10,24,0.6)',
                border: `1px solid ${idx === 0 ? 'rgba(255,225,79,0.35)' : 'rgba(255,255,255,0.06)'}`,
              }}>
                <div style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 14,
                  color: idx === 0 ? '#FFE14F' : 'rgba(247,247,255,0.45)',
                  minWidth: 30,
                }}>
                  {idx + 1}.
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontFamily: 'Space Grotesk, sans-serif',
                    fontSize: 14, fontWeight: 700,
                    color: idx === 0 ? '#FFE14F' : 'rgba(247,247,255,0.85)',
                  }}>
                    {r.name}
                  </div>
                  <div style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 8, letterSpacing: 1.5,
                    color: 'rgba(247,247,255,0.5)', marginTop: 2,
                  }}>
                    {r.placed} TILES · {r.words} WORDS
                  </div>
                </div>
                <div style={{
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 14,
                  color: idx === 0 ? '#FFE14F' : 'var(--arcade-ink, #F7F7FF)',
                }}>
                  {r.score}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════
//                   Shared helpers
// ══════════════════════════════════════════════════════

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

function ActionBtn({ icon, label, onClick, accent = 'var(--arcade-accent, #FFE14F)' }) {
  return (
    <motion.button
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.96 }}
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '8px 14px', borderRadius: 8,
        background: 'rgba(10,10,24,0.7)',
        border: `1px solid color-mix(in srgb, ${accent} 40%, transparent)`,
        color: accent,
        fontFamily: "'Press Start 2P', monospace",
        fontSize: 8, letterSpacing: 1.5,
        cursor: 'pointer',
      }}
    >
      {icon} {label}
    </motion.button>
  );
}

function WinStat({ label, value, accent = '#FFE14F' }) {
  return (
    <div style={{
      padding: '8px 14px', borderRadius: 10,
      background: 'rgba(10,10,24,0.6)',
      border: '1px solid rgba(255,255,255,0.1)',
      textAlign: 'center', minWidth: 80,
    }}>
      <div style={{ fontFamily: "'Press Start 2P', monospace", fontSize: 8, letterSpacing: 1.5, color: 'rgba(247,247,255,0.5)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "'Press Start 2P', monospace", fontSize: 14, color: accent }}>{value}</div>
    </div>
  );
}
