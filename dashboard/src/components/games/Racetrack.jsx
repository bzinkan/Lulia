'use client';
import { useMemo, useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Flag } from 'lucide-react';

/**
 * Racetrack — horizontal racing visual for Quiz Race (and, later, any shell
 * that wants literal forward-motion scoring).
 *
 * PATH 1 (current): progress is derived client-side from `player.score`
 * relative to a theoretical max. No backend changes. When the question
 * pool runs out the shell's normal game_finished handler still fires;
 * the winner is whoever's furthest across. The track renders a checkered
 * finish line at 100% so "leading the race" is obvious even though the
 * game doesn't end the instant someone crosses.
 *
 * PATH 2 (future follow-up): the server emits per-player progress events
 * and fires game_finished when someone hits 1.0. Swap the `deriveProgress`
 * function for a server-authoritative value and this component won't need
 * other changes.
 *
 * Props:
 *   players           — array from shell (each: { player_id, name, avatar, score })
 *   totalQuestions    — number, used for max-score estimate
 *   maxPointsPerQ     — int, default 1000 (Kahoot-like ceiling used by the games crew)
 *   highlightPlayerId — optional id to outline "you" on the student view
 *   compact           — boolean: tighter vertical layout for the student HUD
 *   maxLanes          — cap how many lanes we render (default 8). Extras collapse
 *                       into "+N more" at the bottom of the track.
 */
export default function Racetrack({
  players = [],
  totalQuestions = 15,
  maxPointsPerQ = 1000,
  highlightPlayerId = null,
  compact = false,
  maxLanes = 8,
}) {
  const maxScore = Math.max(1, totalQuestions * maxPointsPerQ);

  // Sort by current progress DESC so the leader is in lane 1 (top).
  const ranked = useMemo(() => {
    const withProgress = (players || []).map(p => ({
      ...p,
      progress: Math.max(0, Math.min(1, (p.score || 0) / maxScore)),
    }));
    withProgress.sort((a, b) => b.progress - a.progress);
    return withProgress;
  }, [players, maxScore]);

  const visible = ranked.slice(0, maxLanes);
  const hidden = ranked.length - visible.length;

  // Detect overtakes by comparing lane index frame-to-frame. When a player's
  // lane rank improves, briefly flash a "sparkle" near their car.
  const prevLaneRef = useRef(new Map());
  const [sparkles, setSparkles] = useState(new Map()); // playerId -> timestamp

  useEffect(() => {
    const next = new Map();
    visible.forEach((p, i) => next.set(p.player_id, i));
    const newSparkles = new Map();
    next.forEach((lane, pid) => {
      const prev = prevLaneRef.current.get(pid);
      if (prev !== undefined && lane < prev) {
        newSparkles.set(pid, Date.now());
      }
    });
    if (newSparkles.size > 0) {
      setSparkles(newSparkles);
      const t = setTimeout(() => setSparkles(new Map()), 800);
      prevLaneRef.current = next;
      return () => clearTimeout(t);
    }
    prevLaneRef.current = next;
  }, [visible]);

  const laneHeight = compact ? 22 : 34;
  const trackHeight = laneHeight * Math.max(1, visible.length) + 14;

  return (
    <div className={compact ? 'racetrack racetrack--compact' : 'racetrack'}>
      {/* Scene header */}
      {!compact && (
        <div className="racetrack__header">
          <span className="racetrack__label">THE RACE</span>
          <span className="racetrack__flagcell">
            <Flag style={{ width: 13, height: 13 }} /> FINISH
          </span>
        </div>
      )}

      {/* Track surface */}
      <div className="racetrack__surface" style={{ height: trackHeight }}>
        {/* Start line */}
        <div className="racetrack__start" />

        {/* Checkered finish stripe */}
        <div className="racetrack__finish" />

        {/* Lane separators (one less than visible lanes) */}
        {visible.slice(0, -1).map((_, i) => (
          <div key={`sep-${i}`}
            className="racetrack__lane-sep"
            style={{ top: laneHeight * (i + 1) + 6 }}
          />
        ))}

        {/* Lane labels + cars */}
        {visible.map((p, i) => {
          const isYou = highlightPlayerId && p.player_id === highlightPlayerId;
          const sparkAt = sparkles.get(p.player_id);
          const hasCrossed = p.progress >= 1;
          return (
            <div key={p.player_id || i} className="racetrack__lane"
              style={{ top: laneHeight * i + 6, height: laneHeight }}>
              {/* Left-side label (truncated name) */}
              <div className="racetrack__name" data-you={isYou || undefined}>
                {(p.name || 'Player').slice(0, 9)}
              </div>

              {/* Car, animated to progress */}
              <motion.div
                className={`racetrack__car ${hasCrossed ? 'racetrack__car--crossed' : ''}`}
                initial={false}
                animate={{ left: `calc(${p.progress * 100}% - 14px)` }}
                transition={{ type: 'spring', stiffness: 180, damping: 22 }}
                style={{
                  background: carColor(i),
                  border: isYou ? '2px solid #FFBE0B' : '2px solid rgba(0,0,0,0.4)',
                  boxShadow: isYou
                    ? '0 0 10px rgba(255,190,11,0.7)'
                    : '0 2px 6px rgba(0,0,0,0.5)',
                }}
                title={`${p.name} — ${Math.round(p.progress * 100)}%`}
              >
                <span className="racetrack__driver">{p.avatar ? p.avatar : '🏎️'}</span>
                {hasCrossed && !compact && (
                  <span className="racetrack__flag" aria-hidden>🏁</span>
                )}
                {sparkAt && (
                  <motion.span
                    key={`spark-${sparkAt}`}
                    className="racetrack__sparkle"
                    initial={{ opacity: 0, scale: 0.5, x: -16 }}
                    animate={{ opacity: [1, 0], scale: [1, 1.8], x: [-16, -30] }}
                    transition={{ duration: 0.7 }}
                    aria-hidden
                  >✦</motion.span>
                )}
              </motion.div>
            </div>
          );
        })}
      </div>

      {hidden > 0 && !compact && (
        <div className="racetrack__overflow">+ {hidden} more racer{hidden === 1 ? '' : 's'} off-screen</div>
      )}

      {/* First-across banner (informational; game still ends when questions run out) */}
      <AnimatePresence>
        {visible[0]?.progress >= 1 && !compact && (
          <motion.div
            className="racetrack__first"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            🏁 {visible[0].name} crosses the line
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* Deterministic color per lane so the leader doesn't swap colors on overtake.
   Palette pulled from the arcade tokens for consistency. */
const LANE_COLORS = [
  '#FF3864', // coral
  '#3A86FF', // teal
  '#FFBE0B', // mustard
  '#2EC4B6', // sage
  '#B6FF39', // lime
  '#FF006E', // pink
  '#8338EC', // purple
  '#F9C74F', // amber
];
function carColor(laneIndex) {
  return LANE_COLORS[laneIndex % LANE_COLORS.length];
}
