'use client';
import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, Navigation, Compass, Globe } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer, winnerCelebration } from '@/lib/confetti';
import { ArcadeChip } from '@/components/games/CabinetStage';

/**
 * Geo Explorer — arcade-cabinet edition (v1 April 2026). NEW SHELL.
 *
 * Atlas teal #2EC4B6 accent from registry. Dark CartoDB map tiles with
 * Leaflet (loaded via CDN to avoid SSR issues). Student reads a location
 * clue, clicks the map to place a pin. Proximity to the correct location
 * determines points via Haversine distance.
 *
 * Renders inside CabinetStage. Interior content only — no full-page bg.
 *
 * Dual mode:
 *   - MAP mode: when question carries geo coords (question.geo = {lat, lng}
 *     or question.metadata?.geo). Student clicks map, distance-scored.
 *   - MCQ fallback: when only question.options[] present, renders standard
 *     MCQ tiles in the atlas-teal theme (identical to History Quest's pattern).
 *
 * Proximity scoring (map mode):
 *   < 50km  → 1000 pts  (BULLSEYE 🎯)
 *   < 200km →  750 pts  (CLOSE)
 *   < 500km →  500 pts  (WARM)
 *   < 1000km→  250 pts  (FAR)
 *   else    →   50 pts  (MISS)
 *
 * Streak tiers:
 *   3 → Navigator    ×1.5  🧭
 *   6 → Cartographer ×2    🗺
 *  10 → Atlas Master ×3    🌍
 *
 * Server contract: map mode calls onAnswer(JSON.stringify({lat, lng}));
 * MCQ fallback calls onAnswer(selected_option) as normal.
 */

const EXPLORER_TIERS = [
  { min: 0,  label: 'EXPLORER',     mult: 1,   icon: '📍' },
  { min: 3,  label: 'NAVIGATOR',    mult: 1.5, icon: '🧭' },
  { min: 6,  label: 'CARTOGRAPHER', mult: 2,   icon: '🗺' },
  { min: 10, label: 'ATLAS MASTER', mult: 3,   icon: '🌍' },
];
function getExplorerTier(streak) {
  for (let i = EXPLORER_TIERS.length - 1; i >= 0; i--) {
    if (streak >= EXPLORER_TIERS[i].min) return EXPLORER_TIERS[i];
  }
  return EXPLORER_TIERS[0];
}
function nextExplorerAt(streak) {
  for (const t of EXPLORER_TIERS) { if (t.min > streak) return t.min; }
  return null;
}

// Haversine distance in km
function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Score from distance
function proximityScore(distKm) {
  if (distKm < 50)   return { pts: 1000, label: 'BULLSEYE', emoji: '🎯', color: '#16D474' };
  if (distKm < 200)  return { pts: 750,  label: 'CLOSE',    emoji: '✓',  color: '#2EC4B6' };
  if (distKm < 500)  return { pts: 500,  label: 'WARM',     emoji: '~',  color: '#FFBE0B' };
  if (distKm < 1000) return { pts: 250,  label: 'FAR',      emoji: '→',  color: '#FF8A6E' };
  return               { pts: 50,   label: 'MISS',     emoji: '✗',  color: '#FF3864' };
}

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];
const MCQ_COLORS = ['#2EC4B6', '#1A8A80', '#3DD6C8', '#16726A'];

// Leaflet CDN URLs
const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
const LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';

export default function GeoExplorer({
  allQuestions = [], question, players = [], view = 'student',
  onAnswer, config = {},
  questionIndex = 0, totalQuestions = 12, lastResult = null, playerId = null,
}) {
  // Extract geo coords from question if available
  const geo = useMemo(() => {
    if (question?.geo) return question.geo;
    if (question?.metadata?.geo) return question.metadata.geo;
    return null;
  }, [question]);

  const isMapMode = !!geo;

  const [guessPos, setGuessPos] = useState(null);     // {lat, lng} from map click
  const [submitted, setSubmitted] = useState(false);
  const [showResult, setShowResult] = useState(null);  // { pts, label, distKm, color }
  const [selectedMcq, setSelectedMcq] = useState(null);
  const [lockedMcq, setLockedMcq] = useState(false);
  const [streak, setStreak] = useState(0);
  const [bestStreak, setBestStreak] = useState(0);
  const [score, setScore] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [wrongCount, setWrongCount] = useState(0);
  const [gameOver, setGameOver] = useState(false);
  const [leafletReady, setLeafletReady] = useState(false);

  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef([]);
  const lineRef = useRef(null);

  // Load Leaflet from CDN
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (window.L) { setLeafletReady(true); return; }

    const link = document.createElement('link');
    link.rel = 'stylesheet'; link.href = LEAFLET_CSS;
    document.head.appendChild(link);

    const script = document.createElement('script');
    script.src = LEAFLET_JS;
    script.onload = () => setLeafletReady(true);
    document.head.appendChild(script);

    return () => {
      // Don't remove — other instances may need it
    };
  }, []);

  // Initialize map
  useEffect(() => {
    if (!leafletReady || !mapRef.current || !isMapMode || view !== 'student') return;
    if (mapInstance.current) return; // already init

    const L = window.L;
    const map = L.map(mapRef.current, {
      center: [20, 0],
      zoom: 2,
      minZoom: 2,
      maxZoom: 18,
      zoomControl: false,
      attributionControl: false,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    // Zoom control on right
    L.control.zoom({ position: 'topright' }).addTo(map);

    mapInstance.current = map;

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, [leafletReady, isMapMode, view]);

  // Clear markers + lines on new question, reset map view
  useEffect(() => {
    setGuessPos(null);
    setSubmitted(false);
    setShowResult(null);
    setSelectedMcq(null);
    setLockedMcq(false);

    if (mapInstance.current) {
      const L = window.L;
      markersRef.current.forEach(m => m.remove());
      markersRef.current = [];
      if (lineRef.current) { lineRef.current.remove(); lineRef.current = null; }
      mapInstance.current.setView([20, 0], 2);
    }
  }, [question?.question_text]);

  // Attach map click handler
  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !isMapMode || submitted) return;

    const L = window.L;
    function onClick(e) {
      // Clear previous guess marker
      markersRef.current.forEach(m => m.remove());
      markersRef.current = [];

      const marker = L.circleMarker([e.latlng.lat, e.latlng.lng], {
        radius: 8,
        fillColor: '#2EC4B6',
        fillOpacity: 0.9,
        color: '#fff',
        weight: 2,
      }).addTo(map);

      markersRef.current.push(marker);
      setGuessPos({ lat: e.latlng.lat, lng: e.latlng.lng });
    }

    map.on('click', onClick);
    return () => map.off('click', onClick);
  }, [isMapMode, submitted]);

  // Submit map guess
  const submitGuess = useCallback(() => {
    if (!guessPos || submitted) return;
    setSubmitted(true);
    play('whoosh');
    onAnswer?.(JSON.stringify(guessPos));
  }, [guessPos, submitted, onAnswer]);

  // MCQ select
  const handleMcqSelect = useCallback((opt) => {
    if (lockedMcq || showResult) return;
    setSelectedMcq(opt);
    setLockedMcq(true);
    play('whoosh');
    setTimeout(() => onAnswer?.(opt), 400);
  }, [lockedMcq, showResult, onAnswer]);

  // Handle result
  useEffect(() => {
    if (!lastResult) return;

    if (isMapMode && guessPos && geo) {
      const distKm = haversineKm(guessPos.lat, guessPos.lng, geo.lat, geo.lng);
      const prox = proximityScore(distKm);
      const tierMult = getExplorerTier(streak + (prox.pts >= 500 ? 1 : 0)).mult;
      const finalPts = Math.round(prox.pts * tierMult);

      setShowResult({ ...prox, distKm: Math.round(distKm), finalPts });

      if (prox.pts >= 500) {
        play('correct');
        correctAnswer({ x: 0.5, y: 0.45 });
        setStreak(s => s + 1);
        setBestStreak(b => Math.max(b, streak + 1));
        setCorrectCount(c => c + 1);
      } else {
        play('incorrect');
        setStreak(0);
        setWrongCount(w => w + 1);
      }
      setScore(s => s + finalPts);

      // Show correct location on map
      if (mapInstance.current && window.L) {
        const L = window.L;
        const correctMarker = L.circleMarker([geo.lat, geo.lng], {
          radius: 10,
          fillColor: '#16D474',
          fillOpacity: 0.9,
          color: '#fff',
          weight: 2,
        }).addTo(mapInstance.current);
        markersRef.current.push(correctMarker);

        // Line from guess to correct
        const line = L.polyline([[guessPos.lat, guessPos.lng], [geo.lat, geo.lng]], {
          color: prox.color,
          weight: 2,
          dashArray: '6, 8',
          opacity: 0.8,
        }).addTo(mapInstance.current);
        lineRef.current = line;

        // Fit both points in view
        const bounds = L.latLngBounds([
          [guessPos.lat, guessPos.lng],
          [geo.lat, geo.lng],
        ]).pad(0.3);
        mapInstance.current.fitBounds(bounds);
      }
    } else {
      // MCQ mode result
      if (lastResult.correct) {
        play('correct');
        correctAnswer({ x: 0.5, y: 0.45 });
        setShowResult({ label: 'CORRECT', color: '#16D474' });
        setStreak(s => s + 1);
        setBestStreak(b => Math.max(b, streak + 1));
        setCorrectCount(c => c + 1);
        const t = getExplorerTier(streak + 1);
        setScore(s => s + Math.round(100 * t.mult));
      } else {
        play('incorrect');
        setShowResult({ label: 'WRONG', color: '#FF3864', correctText: lastResult.correct_answer || question?.answer });
        setStreak(0);
        setWrongCount(w => w + 1);
      }
    }

    const t = setTimeout(() => setShowResult(null), 2500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastResult]);

  // Game over
  useEffect(() => {
    if (questionIndex >= totalQuestions - 1 && lastResult && !gameOver) {
      setTimeout(() => {
        setGameOver(true);
        play('fanfare');
        winnerCelebration();
      }, 2800);
    }
  }, [questionIndex, totalQuestions, lastResult, gameOver]);

  const tier = getExplorerTier(streak);
  const options = question?.options || [];

  // HUD
  const hudLeft = (
    <>
      <ArcadeChip>LOCATION {questionIndex + 1}/{totalQuestions}</ArcadeChip>
      <ArcadeChip variant="ghost">{tier.icon} {tier.label}</ArcadeChip>
    </>
  );
  const hudRight = (
    <>
      <ArcadeChip variant={streak >= 3 ? 'solid' : 'ghost'}>
        ×{tier.mult}
      </ArcadeChip>
      <ArcadeChip variant="ghost">✓{correctCount} ✗{wrongCount}</ArcadeChip>
      <ArcadeChip>SCORE {score}</ArcadeChip>
    </>
  );

  // ── GAME OVER ──
  if (gameOver) {
    return (
      <div style={{ padding: '4px 0 24px', color: 'var(--arcade-ink, #F7F7FF)' }}>
        <StageHudBand left={hudLeft} right={hudRight} />
        <motion.div
          initial={{ opacity: 0, scale: 0.85, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 220, damping: 18 }}
          style={{
            maxWidth: 640, margin: '40px auto',
            padding: '36px 28px', textAlign: 'center',
            background: 'linear-gradient(180deg, rgba(46,196,182,0.15), rgba(10,10,24,0.85))',
            border: '2px solid var(--arcade-accent, #2EC4B6)',
            borderRadius: 18,
            boxShadow: '0 0 40px color-mix(in srgb, var(--arcade-accent, #2EC4B6) 35%, transparent)',
          }}
        >
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 12,
            letterSpacing: 2.5, color: 'var(--arcade-accent, #2EC4B6)', marginBottom: 12,
          }}>
            {correctCount >= totalQuestions * 0.8 ? '★ WORLD TRAVELER ★' : '★ EXPEDITION COMPLETE ★'}
          </div>
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 26,
            letterSpacing: 2, color: '#2EC4B6', marginBottom: 16,
            textShadow: '0 0 18px rgba(46,196,182,0.6)',
          }}>
            {score} PTS
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
            <WinStat label="CORRECT" value={`${correctCount}/${totalQuestions}`} accent="#2EC4B6" />
            <WinStat label="BEST STREAK" value={bestStreak} accent="#2EC4B6" />
            <WinStat label="RANK" value={getExplorerTier(bestStreak).label} accent="#2EC4B6" />
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

        {/* Streak banner */}
        <AnimatePresence>
          {streak >= 3 && (
            <motion.div
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              style={{
                textAlign: 'center', marginBottom: 8,
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 10, letterSpacing: 2.5, color: '#2EC4B6',
              }}
            >
              {tier.icon} {tier.label} ×{tier.mult} {tier.icon}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Clue card */}
        <div style={{
          maxWidth: 720, margin: '0 auto 12px',
          padding: '16px 20px',
          borderRadius: 14,
          background: `
            radial-gradient(circle at 50% 0%, rgba(46,196,182,0.12), transparent 55%),
            linear-gradient(180deg, #0F0F24, #0A0A1A)`,
          border: '2px solid color-mix(in srgb, var(--arcade-accent, #2EC4B6) 55%, transparent)',
          boxShadow: '0 0 20px rgba(46,196,182,0.2)',
          textAlign: 'center',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 8,
          }}>
            <Compass style={{ width: 14, height: 14, color: '#2EC4B6' }} />
            <span style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 9, letterSpacing: 2, color: '#2EC4B6',
            }}>
              CLUE {questionIndex + 1}
            </span>
          </div>
          <div style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontWeight: 700, fontSize: 'clamp(20px, 4vw, 28px)',
            lineHeight: 1.25, color: '#E1FFF9',
            textShadow: '0 0 10px rgba(46,196,182,0.2)',
          }}>
            {question?.question_text || 'Loading clue...'}
          </div>
        </div>

        {/* MAP MODE */}
        {isMapMode ? (
          <div style={{ maxWidth: 720, margin: '0 auto' }}>
            {/* Map container */}
            <div style={{
              height: 380,
              borderRadius: 14,
              overflow: 'hidden',
              border: '2px solid color-mix(in srgb, var(--arcade-accent, #2EC4B6) 40%, transparent)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              position: 'relative',
            }}>
              <div ref={mapRef} style={{ width: '100%', height: '100%' }} />

              {/* Result overlay on map */}
              <AnimatePresence>
                {showResult && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    style={{
                      position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
                      padding: '10px 18px', borderRadius: 12, zIndex: 1000,
                      background: 'rgba(10,10,24,0.9)',
                      border: `2px solid ${showResult.color}`,
                      boxShadow: `0 0 20px ${showResult.color}40`,
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 11, letterSpacing: 1.5,
                      color: showResult.color,
                      textAlign: 'center',
                    }}
                  >
                    <div>{showResult.emoji} {showResult.label}</div>
                    <div style={{ fontSize: 9, marginTop: 4, color: 'rgba(247,247,255,0.7)' }}>
                      {showResult.distKm} km away · +{showResult.finalPts} pts
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Click hint */}
              {!guessPos && !submitted && (
                <div style={{
                  position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
                  padding: '6px 14px', borderRadius: 999, zIndex: 1000,
                  background: 'rgba(10,10,24,0.85)',
                  border: '1px solid rgba(46,196,182,0.4)',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 9, letterSpacing: 1.5, color: '#2EC4B6',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <MapPin style={{ width: 12, height: 12 }} /> TAP THE MAP
                </div>
              )}
            </div>

            {/* Confirm button */}
            {guessPos && !submitted && (
              <motion.button
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                whileTap={{ scale: 0.95 }}
                onClick={submitGuess}
                style={{
                  display: 'block', width: '100%', maxWidth: 300,
                  margin: '14px auto 0',
                  padding: '14px 20px',
                  borderRadius: 12, border: 'none',
                  background: 'linear-gradient(180deg, #2EC4B6, #1A8A80)',
                  color: '#0A0A18',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 12, letterSpacing: 1.5,
                  cursor: 'pointer',
                  boxShadow: '0 0 16px rgba(46,196,182,0.4), 0 4px 0 #16726A, 0 6px 14px rgba(0,0,0,0.5)',
                }}
              >
                <Navigation style={{ width: 14, height: 14, display: 'inline', marginRight: 8, verticalAlign: 'middle' }} />
                LOCK IN GUESS
              </motion.button>
            )}
          </div>
        ) : (
          /* MCQ FALLBACK MODE */
          <div style={{
            maxWidth: 720, margin: '0 auto',
            display: 'grid',
            gridTemplateColumns: options.length <= 2 ? '1fr' : 'repeat(2, 1fr)',
            gap: 10,
          }}>
            {options.map((opt, i) => {
              const isSelected = selectedMcq === opt;
              const isCorrectOpt = showResult && opt === (question?.answer || '');
              const isWrongSel = showResult?.label === 'WRONG' && isSelected;
              const isDisabled = lockedMcq || !!showResult;

              let bg = `linear-gradient(180deg, ${MCQ_COLORS[i % MCQ_COLORS.length]}, color-mix(in srgb, ${MCQ_COLORS[i % MCQ_COLORS.length]} 70%, black 30%))`;
              if (isCorrectOpt) bg = 'linear-gradient(180deg, #16D474, #0F9B4F)';
              if (isWrongSel) bg = 'linear-gradient(180deg, #FF3864, #CC2040)';

              return (
                <motion.button
                  key={opt}
                  onClick={() => handleMcqSelect(opt)}
                  disabled={isDisabled}
                  whileHover={!isDisabled ? { scale: 1.02, y: -1 } : {}}
                  whileTap={!isDisabled ? { scale: 0.97 } : {}}
                  animate={isWrongSel ? { x: [-2, 2, -2, 2, 0] } : isCorrectOpt ? { scale: [1, 1.04, 1] } : {}}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '14px 16px', borderRadius: 12,
                    background: bg, color: '#0A0A18',
                    fontFamily: 'Space Grotesk, sans-serif',
                    fontWeight: 700, fontSize: 14, textAlign: 'left',
                    cursor: isDisabled ? 'default' : 'pointer',
                    border: isSelected && !showResult ? '2px solid rgba(255,255,255,0.9)' : '2px solid transparent',
                    boxShadow: '0 4px 0 rgba(0,0,0,0.3), 0 6px 14px rgba(0,0,0,0.4)',
                    opacity: isDisabled && !isSelected && !isCorrectOpt ? 0.5 : 1,
                  }}
                >
                  <span style={{ fontFamily: "'Press Start 2P', monospace", fontSize: 11, minWidth: 22, color: 'rgba(10,10,24,0.6)' }}>
                    {LETTERS[i]}
                  </span>
                  <span style={{ flex: 1, lineHeight: 1.3 }}>{opt}</span>
                </motion.button>
              );
            })}
            {showResult?.correctText && (
              <div style={{
                gridColumn: '1 / -1', textAlign: 'center', marginTop: 8,
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 10, letterSpacing: 1.5, color: '#FF3864',
              }}>
                ✗ CORRECT: {showResult.correctText}
              </div>
            )}
          </div>
        )}

        {/* Streak hint */}
        {streak >= 1 && streak < 10 && (
          <div style={{
            textAlign: 'center', marginTop: 14,
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 9, letterSpacing: 2,
            color: streak >= 3 ? '#2EC4B6' : 'rgba(247,247,255,0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
            <Globe style={{ width: 12, height: 12 }} />
            STREAK {streak} {nextExplorerAt(streak) ? `— NEXT RANK AT ${nextExplorerAt(streak)}` : ''}
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
        geo={geo}
      />
    </div>
  );
}

// ============================================================
//              TeacherBoard
// ============================================================

function TeacherBoard({ question, questionIndex, totalQuestions, players, geo }) {
  const rows = useMemo(() => {
    return (players || []).map(p => ({
      id: p.player_id || p.id,
      name: p.name || p.display_name || 'Player',
      score: p.score || 0,
      correct: p.answers_correct ?? 0,
      streak: p.current_streak ?? 0,
    })).sort((a, b) => b.score - a.score);
  }, [players]);

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div style={{
        padding: '20px 24px', marginBottom: 16,
        borderRadius: 14, textAlign: 'center',
        background: `radial-gradient(circle at 50% 0%, rgba(46,196,182,0.12), transparent 55%),
          linear-gradient(180deg, #0F0F24, #0A0A1A)`,
        border: '2px solid var(--arcade-accent, #2EC4B6)',
        boxShadow: '0 0 24px rgba(46,196,182,0.2)',
      }}>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2, color: 'var(--arcade-ink-dim, #B6B7D8)', marginBottom: 8,
        }}>
          CLUE {questionIndex + 1} OF {totalQuestions}
        </div>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 24, fontWeight: 700, color: '#E1FFF9',
          textShadow: '0 0 10px rgba(46,196,182,0.2)',
        }}>
          {question?.question_text || 'Waiting...'}
        </div>
        {question?.answer && (
          <div style={{
            marginTop: 8, fontFamily: "'Press Start 2P', monospace",
            fontSize: 12, color: '#2EC4B6',
          }}>
            → {question.answer}
          </div>
        )}
        {geo && (
          <div style={{
            marginTop: 4, fontFamily: "'Press Start 2P', monospace",
            fontSize: 9, color: 'rgba(247,247,255,0.5)',
          }}>
            📍 {geo.lat.toFixed(2)}, {geo.lng.toFixed(2)}
          </div>
        )}
      </div>

      <div style={{
        padding: '16px 18px', borderRadius: 14,
        background: 'linear-gradient(180deg, rgba(10,10,24,0.75), rgba(10,10,24,0.55))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2, color: 'var(--arcade-accent, #2EC4B6)', marginBottom: 12,
        }}>
          EXPEDITION · {rows.length} EXPLORER{rows.length === 1 ? '' : 'S'}
        </div>
        {rows.length === 0 ? (
          <div style={{ fontSize: 13, color: 'rgba(247,247,255,0.55)' }}>
            Waiting for explorers to place their pins…
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rows.map((r, idx) => {
              const t = getExplorerTier(r.streak);
              return (
                <div key={r.id} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '10px 14px', borderRadius: 10,
                  background: idx === 0 ? 'linear-gradient(90deg, rgba(46,196,182,0.12), rgba(10,10,24,0.7))' : 'rgba(10,10,24,0.6)',
                  border: `1px solid ${idx === 0 ? 'rgba(46,196,182,0.35)' : 'rgba(255,255,255,0.06)'}`,
                }}>
                  <div style={{ fontFamily: "'Press Start 2P', monospace", fontSize: 14, color: idx === 0 ? '#2EC4B6' : 'rgba(247,247,255,0.45)', minWidth: 30 }}>
                    {idx + 1}.
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: 'Space Grotesk, sans-serif', fontSize: 14, fontWeight: 700, color: idx === 0 ? '#2EC4B6' : 'rgba(247,247,255,0.85)' }}>
                      {r.name}
                    </div>
                    <div style={{ fontFamily: "'Press Start 2P', monospace", fontSize: 8, letterSpacing: 1.5, color: 'rgba(247,247,255,0.5)', marginTop: 2 }}>
                      {t.icon} {t.label}{r.streak >= 3 ? ` · STREAK ${r.streak}` : ''}
                    </div>
                  </div>
                  <div style={{ fontFamily: "'Press Start 2P', monospace", fontSize: 14, color: idx === 0 ? '#2EC4B6' : 'var(--arcade-ink, #F7F7FF)' }}>
                    {r.score}
                  </div>
                  <div style={{ fontFamily: "'Press Start 2P', monospace", fontSize: 9, color: 'rgba(247,247,255,0.5)', minWidth: 40, textAlign: 'right' }}>
                    ✓{r.correct}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
//                    Shared helpers
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

function WinStat({ label, value, accent = '#2EC4B6' }) {
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
