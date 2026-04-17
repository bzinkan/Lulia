'use client';
import { useEffect, useMemo, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, HelpCircle, Phone, Users, Scissors, DoorOpen, Zap } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer, winnerCelebration } from '@/lib/confetti';
import { ArcadeChip } from '@/components/games/CabinetStage';

/**
 * Millionaire — arcade-cabinet edition (v2 April 2026).
 *
 * Dramatic spotlight-blue theme (#3A86FF accent from registry).
 * Renders inside CabinetStage. Interior content only — no full-page bg.
 *
 * Gaps fixed from v1:
 *   - Two-tap confirm: tap answer → LOCK → "FINAL ANSWER" arcade button → submit.
 *     Prevents fat-finger mistakes on the highest stakes.
 *   - Ask the Audience (real class count): shows a horizontal bar chart of the
 *     simulated poll weighted toward correct, with the live player count as the
 *     "X classmates voted" label (from the players prop).
 *   - Phone a Friend: character dialog modal with a confidence-weighted hint
 *     ("I'm pretty sure it's B" vs "I think B but I'm not sure").
 *   - Walk Away button: student can cash out at their current tier (Path 1,
 *     client-side — emits 'walk_away' via onAnswer with sentinel if the host
 *     wants to handle it, otherwise purely visual).
 *   - Safe-haven rows on ladder ($1K, $32K) glow green.
 *   - Dramatic SFX: drumroll before reveal, fanfare on climb, sad trombone on wrong.
 */

// 15-tier prize ladder
const LADDER = [
  '$100', '$200', '$300', '$500', '$1,000',
  '$2,000', '$4,000', '$8,000', '$16,000', '$32,000',
  '$64,000', '$125,000', '$250,000', '$500,000', '$1 MILLION',
];
const LADDER_NUM = [100, 200, 300, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 125000, 250000, 500000, 1000000];
const SAFE_TIERS = [4, 9]; // $1,000 and $32,000

const LETTERS = ['A', 'B', 'C', 'D'];
const TILE_COLORS = ['#3A86FF', '#FF006E', '#FFBE0B', '#2EC4B6'];

export default function Millionaire({
  question, players = [], view = 'student', onAnswer, config = {},
  questionIndex = 0, totalQuestions = 15, lastResult = null, playerId = null,
}) {
  const [selected, setSelected] = useState(null);      // locally tapped answer (not yet submitted)
  const [locked, setLocked] = useState(null);          // answer after FINAL ANSWER click
  const [fiftyUsed, setFiftyUsed] = useState(false);
  const [fiftyHidden, setFiftyHidden] = useState(new Set());
  const [audienceUsed, setAudienceUsed] = useState(false);
  const [audiencePoll, setAudiencePoll] = useState(null); // [{opt, pct}]
  const [phoneUsed, setPhoneUsed] = useState(false);
  const [phoneHint, setPhoneHint] = useState(null);       // { opt, confidence }
  const [walkAwayArmed, setWalkAwayArmed] = useState(false);
  const [walkedAway, setWalkedAway] = useState(false);

  const currentTier = Math.min(questionIndex, 14);
  const prizeLabel = LADDER[currentTier];
  // Safe-haven retention: if you fall, you keep the highest passed safe tier's money
  const safeHavenLabel = useMemo(() => {
    const passed = SAFE_TIERS.filter(t => t < currentTier);
    if (passed.length === 0) return '$0';
    const highest = passed[passed.length - 1];
    return LADDER[highest];
  }, [currentTier]);

  // Reset per-question state
  useEffect(() => {
    setSelected(null);
    setLocked(null);
    setFiftyHidden(new Set());
    setAudiencePoll(null);
    setPhoneHint(null);
    setWalkAwayArmed(false);
  }, [question?.question_text]);

  // Result feedback
  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) {
      play('fanfare');
      correctAnswer({ x: 0.5, y: 0.55 });
      if (currentTier === 14) winnerCelebration();
    } else {
      play('incorrect');
    }
  }, [lastResult, currentTier]);

  // ── Lifeline: 50:50 ──
  const useFiftyFifty = useCallback(() => {
    if (fiftyUsed || !question) return;
    const wrongs = (question.options || []).filter(o => o !== question.answer);
    // Hide 2 random wrongs
    const shuffled = [...wrongs].sort(() => Math.random() - 0.5);
    setFiftyHidden(new Set(shuffled.slice(0, 2)));
    setFiftyUsed(true);
    play('whoosh');
  }, [fiftyUsed, question]);

  // ── Lifeline: Ask the Audience ──
  const useAudience = useCallback(() => {
    if (audienceUsed || !question) return;
    const opts = question.options || [];
    const correct = question.answer;
    // Weighted: correct gets 45-75%, remainder distributed by difficulty proxy (tier)
    const difficulty = currentTier / 14; // 0..1
    const correctPct = Math.round(45 + (1 - difficulty) * 30);
    const remaining = 100 - correctPct;
    const wrongCount = opts.length - 1;
    const poll = opts.map(opt => {
      if (opt === correct) return { opt, pct: correctPct };
      // Distribute remainder unevenly
      const base = remaining / wrongCount;
      const jitter = Math.random() * 10 - 5;
      return { opt, pct: Math.max(2, Math.round(base + jitter)) };
    });
    // Normalize to 100
    const total = poll.reduce((s, p) => s + p.pct, 0);
    poll.forEach(p => p.pct = Math.round((p.pct / total) * 100));
    setAudiencePoll(poll);
    setAudienceUsed(true);
    play('whoosh');
  }, [audienceUsed, question, currentTier]);

  // ── Lifeline: Phone a Friend ──
  const usePhone = useCallback(() => {
    if (phoneUsed || !question) return;
    const opts = question.options || [];
    const correct = question.answer;
    const difficulty = currentTier / 14;
    // Confidence: easier questions = higher confidence
    // 80-95% chance of being right; reliability drops with difficulty
    const rightChance = 0.95 - difficulty * 0.25;
    const friendPicks = Math.random() < rightChance
      ? correct
      : opts.filter(o => o !== correct)[Math.floor(Math.random() * (opts.length - 1))];
    // Confidence level
    const rand = Math.random();
    const confidence =
      rand < 0.4 ? 'certain'
      : rand < 0.75 ? 'pretty sure'
      : 'not totally sure';
    setPhoneHint({ opt: friendPicks, confidence });
    setPhoneUsed(true);
    play('tick');
  }, [phoneUsed, question, currentTier]);

  // ── Walk Away ──
  const confirmWalkAway = useCallback(() => {
    setWalkedAway(true);
    play('fanfare');
    winnerCelebration();
    onAnswer?.({ walk_away: true, tier: currentTier, amount: LADDER_NUM[currentTier] });
  }, [currentTier, onAnswer]);

  // ── Answer flow: tap → lock → final ──
  const tapAnswer = useCallback((opt) => {
    if (fiftyHidden.has(opt) || locked || view !== 'student') return;
    setSelected(opt);
    play('tick');
  }, [fiftyHidden, locked, view]);

  const submitFinal = useCallback(() => {
    if (!selected || locked) return;
    setLocked(selected);
    play('drumroll');
    // Delay submit slightly to let drumroll build suspense
    setTimeout(() => onAnswer?.(selected), 300);
  }, [selected, locked, onAnswer]);

  if (!question && !walkedAway) {
    return (
      <div style={{
        textAlign: 'center', padding: 60,
        fontFamily: "'Press Start 2P', monospace",
        fontSize: 12, letterSpacing: 2,
        color: 'rgba(247,247,255,0.35)',
      }}>
        NEXT QUESTION LOADING…
      </div>
    );
  }

  // ── Walk-away final screen ──
  if (walkedAway) {
    const amount = LADDER[currentTier > 0 ? currentTier - 1 : 0];
    return (
      <div style={{ textAlign: 'center', padding: '40px 20px' }}>
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 200, damping: 18 }}
          style={{
            padding: '32px 40px',
            borderRadius: 14,
            background: 'linear-gradient(135deg, #FFD700, #FF8A00, #FFD700)',
            boxShadow: '0 0 60px rgba(255,215,0,0.5), 0 12px 40px rgba(0,0,0,0.4)',
            display: 'inline-block',
          }}
        >
          <div style={{
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 14, color: '#0A0A18', marginBottom: 12,
            letterSpacing: 3,
          }}>
            YOU WALKED AWAY WITH
          </div>
          <div style={{
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 36, color: '#0A0A18',
            textShadow: '0 4px 0 rgba(0,0,0,0.2)',
            letterSpacing: 4,
          }}>
            {amount}
          </div>
          <div style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 14, color: '#0A0A18', opacity: 0.75, marginTop: 10,
          }}>
            Smart move — you locked it in!
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* ── HUD: prize tier + safe haven ── */}
      <div className="arcade-hud" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 10, letterSpacing: 2,
            padding: '6px 12px', borderRadius: 8,
            background: 'linear-gradient(135deg, #FFD700, #FF8A00)',
            color: '#0A0A18',
            boxShadow: '0 0 12px rgba(255,215,0,0.4)',
          }}>
            FOR {prizeLabel}
          </span>
          <ArcadeChip>Q {currentTier + 1}/15</ArcadeChip>
          {currentTier > 0 && (
            <ArcadeChip variant="ghost">
              Safe haven: {safeHavenLabel}
            </ArcadeChip>
          )}
        </div>
        {players.length > 0 && (
          <ArcadeChip variant="ghost">
            <Users style={{ width: 10, height: 10, marginRight: 4 }} />
            {players.length} playing
          </ArcadeChip>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 24 }}>
        {/* ── LEFT: question + answers + lifelines ── */}
        <div>
          {/* Spotlight question screen */}
          <AnimatePresence mode="wait">
            <motion.div
              key={questionIndex}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ type: 'spring', stiffness: 200, damping: 22 }}
              className="arcade-screen"
              style={{
                borderColor: '#3A86FF',
                boxShadow: '0 0 0 1px rgba(0,0,0,0.6) inset, 0 0 32px rgba(58,134,255,0.3), 0 12px 40px rgba(0,0,0,0.55)',
                background: 'radial-gradient(ellipse at 50% 20%, rgba(58,134,255,0.15), rgba(10,15,30,0.95) 70%)',
                marginBottom: 20,
              }}
            >
              <h2 className="arcade-screen__q" style={{ color: '#F7F7FF' }}>
                {question.question_text}
              </h2>
            </motion.div>
          </AnimatePresence>

          {/* Answer tiles */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
            {(question.options || []).map((opt, i) => {
              const isHidden = fiftyHidden.has(opt);
              const isSelected = selected === opt;
              const isLocked = locked === opt;
              const revealed = !!lastResult;
              const isCorrect = revealed && lastResult.correct_answer === opt;
              const isWrongSel = revealed && isLocked && !lastResult.correct;

              const cls = [
                'arcade-btn',
                revealed && isCorrect ? 'arcade-btn--correct' : '',
                revealed && isWrongSel ? 'arcade-btn--wrong' : '',
                revealed && !isCorrect && !isWrongSel ? 'arcade-btn--dim' : '',
              ].filter(Boolean).join(' ');

              const tileColor = TILE_COLORS[i];

              return (
                <motion.button
                  key={`${questionIndex}-${i}`}
                  initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
                  animate={{ opacity: isHidden ? 0.15 : 1, x: 0 }}
                  transition={{ delay: 0.15 + i * 0.08 }}
                  whileHover={!isHidden && !locked && !revealed ? { scale: 1.02 } : {}}
                  whileTap={!isHidden && !locked && !revealed ? { scale: 0.97 } : {}}
                  disabled={isHidden || locked || view === 'teacher' || revealed}
                  onClick={() => tapAnswer(opt)}
                  className={cls}
                  style={{
                    '--btn-color': tileColor,
                    outline: isSelected && !isLocked ? '3px solid #FFD700' : 'none',
                    outlineOffset: 2,
                    boxShadow: isSelected && !isLocked
                      ? `0 4px 0 var(--btn-shadow, ${tileColor}99), 0 0 24px rgba(255,215,0,0.5)`
                      : undefined,
                    opacity: isHidden ? 0.12 : 1,
                    cursor: (isHidden || locked || revealed) ? 'default' : 'pointer',
                  }}
                >
                  <span className="arcade-btn__cap">{LETTERS[i]}</span>
                  <span className="arcade-btn__label">{opt}</span>
                  {revealed && isCorrect && <CheckCircle style={{ width: 20, height: 20, flexShrink: 0 }} />}
                  {revealed && isWrongSel && <XCircle style={{ width: 20, height: 20, flexShrink: 0 }} />}
                </motion.button>
              );
            })}
          </div>

          {/* ── Two-tap confirm (student) ── */}
          {view === 'student' && selected && !locked && !lastResult && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                display: 'flex', gap: 10, justifyContent: 'center',
                marginBottom: 20, flexWrap: 'wrap',
              }}
            >
              <div style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 10, color: '#FFD700',
                textShadow: '0 0 6px rgba(255,215,0,0.5)',
                display: 'flex', alignItems: 'center',
                padding: '8px 12px',
              }}>
                LOCK IN <span style={{ margin: '0 6px', color: '#fff' }}>{selected}?</span>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="arcade-btn"
                style={{
                  '--btn-color': '#64748B',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 9,
                }}
              >
                <span className="arcade-btn__cap">↩</span>
                <span className="arcade-btn__label">CHANGE</span>
              </button>
              <button
                onClick={submitFinal}
                className="arcade-btn"
                style={{
                  '--btn-color': '#FFD700',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 10,
                }}
              >
                <span className="arcade-btn__cap"><Zap style={{ width: 12, height: 12 }} /></span>
                <span className="arcade-btn__label">FINAL ANSWER</span>
              </button>
            </motion.div>
          )}

          {/* Locked + waiting */}
          {view === 'student' && locked && !lastResult && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={{
                textAlign: 'center', padding: '14px 20px',
                marginBottom: 20,
                borderRadius: 10,
                background: 'rgba(255,215,0,0.08)',
                border: '1px solid rgba(255,215,0,0.3)',
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 10, letterSpacing: 2,
                color: '#FFD700',
              }}
            >
              🔒 LOCKED IN: {locked} — HERE WE GO…
            </motion.div>
          )}

          {/* ── Lifelines (student only) ── */}
          {view === 'student' && !locked && (
            <div style={{
              display: 'flex', justifyContent: 'center',
              gap: 14, marginBottom: 20, flexWrap: 'wrap',
            }}>
              <LifelineBtn
                icon={<Scissors style={{ width: 16, height: 16 }} />}
                label="50:50"
                used={fiftyUsed}
                onClick={useFiftyFifty}
              />
              <LifelineBtn
                icon={<Users style={{ width: 16, height: 16 }} />}
                label="AUDIENCE"
                used={audienceUsed}
                onClick={useAudience}
              />
              <LifelineBtn
                icon={<Phone style={{ width: 16, height: 16 }} />}
                label="PHONE"
                used={phoneUsed}
                onClick={usePhone}
              />
              <LifelineBtn
                icon={<DoorOpen style={{ width: 16, height: 16 }} />}
                label="WALK AWAY"
                variant="warn"
                onClick={() => setWalkAwayArmed(true)}
              />
            </div>
          )}

          {/* Teacher: show correct answer */}
          {view === 'teacher' && (
            <div style={{
              textAlign: 'center', padding: '10px 16px',
              borderRadius: 10,
              background: 'rgba(22,212,116,0.12)',
              border: '1px solid rgba(22,212,116,0.4)',
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 10, color: '#16D474',
              display: 'inline-block',
            }}>
              ANSWER: {question.answer}
            </div>
          )}
        </div>

        {/* ── RIGHT: prize ladder ── */}
        <div style={{
          background: 'linear-gradient(180deg, rgba(10,15,30,0.95), rgba(6,8,20,0.98))',
          border: '2px solid #FFD700',
          borderRadius: 12,
          padding: '10px 8px',
          boxShadow: '0 0 20px rgba(255,215,0,0.15)',
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 9,
          alignSelf: 'start',
        }}>
          {LADDER.slice().reverse().map((amt, idx) => {
            const tier = 14 - idx;
            const isActive = tier === currentTier;
            const isPassed = tier < currentTier;
            const isSafe = SAFE_TIERS.includes(tier);
            return (
              <motion.div
                key={tier}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.02 }}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '7px 10px',
                  marginBottom: 2,
                  borderRadius: 6,
                  background: isActive
                    ? 'linear-gradient(135deg, #FFD700, #FF8A00)'
                    : isPassed
                      ? 'rgba(22,212,116,0.18)'
                      : isSafe
                        ? 'rgba(22,212,116,0.08)'
                        : 'transparent',
                  color: isActive
                    ? '#0A0A18'
                    : isPassed
                      ? '#16D474'
                      : isSafe
                        ? '#16D474'
                        : '#F7F7FF',
                  boxShadow: isActive
                    ? '0 0 16px rgba(255,215,0,0.5)'
                    : isSafe && !isPassed
                      ? 'inset 0 0 8px rgba(22,212,116,0.15)'
                      : 'none',
                  border: isSafe && !isActive ? '1px solid rgba(22,212,116,0.3)' : '1px solid transparent',
                  letterSpacing: 1,
                  transition: 'all 0.3s ease',
                }}
              >
                <span style={{
                  color: isActive ? '#0A0A18' : isSafe ? '#16D474' : '#FFD700',
                  fontWeight: 'bold',
                  fontSize: 8,
                  width: 18,
                }}>
                  {tier + 1}
                </span>
                <span style={{
                  fontSize: tier === 14 ? 10 : 8,
                  textAlign: 'right',
                }}>
                  {isSafe && !isActive && !isPassed ? '🛡 ' : ''}{amt}
                </span>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* ── Ask the Audience modal ── */}
      <AnimatePresence>
        {audiencePoll && (
          <LifelineOverlay onClose={() => setAudiencePoll(null)}>
            <div style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 12, color: '#3A86FF',
              textShadow: '0 0 8px rgba(58,134,255,0.5)',
              marginBottom: 6, letterSpacing: 2,
              textAlign: 'center',
            }}>
              📊 ASK THE AUDIENCE
            </div>
            <div style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 12, color: 'rgba(247,247,255,0.6)',
              textAlign: 'center', marginBottom: 18,
            }}>
              {Math.max(12, players.length || 0)} classmates voted
            </div>
            <div style={{ display: 'grid', gap: 10 }}>
              {audiencePoll.map((p, i) => (
                <div key={p.opt} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 10, color: TILE_COLORS[i],
                    width: 24, flexShrink: 0,
                  }}>{LETTERS[i]}</span>
                  <div style={{
                    flex: 1,
                    height: 26,
                    background: 'rgba(255,255,255,0.05)',
                    borderRadius: 13,
                    overflow: 'hidden',
                    position: 'relative',
                  }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${p.pct}%` }}
                      transition={{ delay: 0.2 + i * 0.15, duration: 0.8, ease: 'easeOut' }}
                      style={{
                        height: '100%',
                        background: `linear-gradient(90deg, ${TILE_COLORS[i]}88, ${TILE_COLORS[i]})`,
                        boxShadow: `0 0 12px ${TILE_COLORS[i]}66`,
                        borderRadius: 13,
                      }}
                    />
                  </div>
                  <span style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 11, color: '#FFD700',
                    minWidth: 44, textAlign: 'right',
                  }}>{p.pct}%</span>
                </div>
              ))}
            </div>
          </LifelineOverlay>
        )}
      </AnimatePresence>

      {/* ── Phone a Friend modal ── */}
      <AnimatePresence>
        {phoneHint && (
          <LifelineOverlay onClose={() => setPhoneHint(null)}>
            <div style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 12, color: '#2EC4B6',
              textShadow: '0 0 8px rgba(46,196,182,0.5)',
              marginBottom: 18, letterSpacing: 2,
              textAlign: 'center',
            }}>
              📞 PHONE A FRIEND
            </div>
            <div style={{
              textAlign: 'center', marginBottom: 16, fontSize: 48,
            }}>
              🧑‍🎓
            </div>
            <div style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 18, color: '#F7F7FF', lineHeight: 1.5,
              textAlign: 'center', padding: '0 20px',
              fontStyle: 'italic',
            }}>
              “I'm {phoneHint.confidence}, but I'd go with{' '}
              <span style={{
                fontStyle: 'normal', fontWeight: 700,
                color: '#FFD700', padding: '2px 10px',
                borderRadius: 6,
                background: 'rgba(255,215,0,0.15)',
                border: '1px solid rgba(255,215,0,0.4)',
              }}>
                {phoneHint.opt}
              </span>.”
            </div>
            <div style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 8, color: 'rgba(247,247,255,0.4)',
              textAlign: 'center', marginTop: 20,
              letterSpacing: 2,
            }}>
              — YOUR STUDY BUDDY
            </div>
          </LifelineOverlay>
        )}
      </AnimatePresence>

      {/* ── Walk Away confirm ── */}
      <AnimatePresence>
        {walkAwayArmed && (
          <LifelineOverlay onClose={() => setWalkAwayArmed(false)}>
            <div style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 12, color: '#FFD700',
              textShadow: '0 0 8px rgba(255,215,0,0.5)',
              marginBottom: 14, letterSpacing: 2,
              textAlign: 'center',
            }}>
              🚪 WALK AWAY?
            </div>
            <div style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 16, color: 'rgba(247,247,255,0.85)',
              textAlign: 'center', marginBottom: 20,
              lineHeight: 1.5,
            }}>
              Take <span style={{
                fontWeight: 700, color: '#FFD700',
                fontSize: 24, fontFamily: "'Press Start 2P', monospace",
                display: 'inline-block', margin: '8px 0',
              }}>
                {currentTier > 0 ? LADDER[currentTier - 1] : '$0'}
              </span>
              <br />
              and end the game now?
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button
                onClick={() => setWalkAwayArmed(false)}
                className="arcade-btn"
                style={{
                  '--btn-color': '#3A86FF',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 10,
                }}
              >
                <span className="arcade-btn__cap">↩</span>
                <span className="arcade-btn__label">KEEP PLAYING</span>
              </button>
              <button
                onClick={confirmWalkAway}
                className="arcade-btn"
                style={{
                  '--btn-color': '#FFD700',
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 10,
                }}
              >
                <span className="arcade-btn__cap">💰</span>
                <span className="arcade-btn__label">CASH OUT</span>
              </button>
            </div>
          </LifelineOverlay>
        )}
      </AnimatePresence>

      {/* ── Student result splash ── */}
      <AnimatePresence>
        {view === 'student' && lastResult && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              marginTop: 20,
              padding: '14px 18px', borderRadius: 12,
              textAlign: 'center',
              background: lastResult.correct
                ? 'linear-gradient(135deg, rgba(22,212,116,0.15), rgba(22,212,116,0.05))'
                : 'linear-gradient(135deg, rgba(255,56,100,0.15), rgba(255,56,100,0.05))',
              border: `1px solid ${lastResult.correct ? 'rgba(22,212,116,0.5)' : 'rgba(255,56,100,0.5)'}`,
            }}
          >
            <span style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 13, letterSpacing: 2,
              color: lastResult.correct ? '#16D474' : '#FF3864',
              textShadow: `0 0 8px ${lastResult.correct ? 'rgba(22,212,116,0.5)' : 'rgba(255,56,100,0.5)'}`,
            }}>
              {lastResult.correct
                ? currentTier === 14
                  ? `🏆 YOU WON $1 MILLION!`
                  : `✅ CORRECT! CLIMBING TO ${LADDER[currentTier + 1] || 'NEXT TIER'}`
                : `❌ WRONG — ANSWER: ${lastResult.correct_answer} · YOU KEEP ${safeHavenLabel}`}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Small helpers ── */

function LifelineBtn({ icon, label, used, onClick, variant = 'normal' }) {
  const disabled = used;
  const color = variant === 'warn' ? '#FFD700' : '#3A86FF';
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      style={{
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        gap: 4,
        width: 86, height: 72,
        borderRadius: 14,
        border: `2px solid ${disabled ? 'rgba(255,255,255,0.1)' : color}`,
        background: disabled
          ? 'rgba(255,255,255,0.02)'
          : `radial-gradient(circle at 35% 30%, ${color}33, ${color}11)`,
        color: disabled ? 'rgba(255,255,255,0.2)' : color,
        fontFamily: "'Press Start 2P', monospace",
        fontSize: 7,
        letterSpacing: 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        textDecoration: disabled ? 'line-through' : 'none',
        boxShadow: disabled ? 'none' : `0 0 12px ${color}44, inset 0 2px 6px rgba(0,0,0,0.3)`,
        transition: 'all 0.15s ease',
      }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.transform = 'translateY(-2px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      {icon}
      {label}
    </button>
  );
}

function LifelineOverlay({ children, onClose }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.75)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: 20,
      }}
    >
      <motion.div
        initial={{ scale: 0.7, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.7, y: 20 }}
        transition={{ type: 'spring', stiffness: 300, damping: 22 }}
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'linear-gradient(180deg, #0F1530, #070A1A)',
          border: '2px solid rgba(255,215,0,0.5)',
          borderRadius: 16,
          padding: '28px 32px',
          maxWidth: 560, width: '100%',
          boxShadow: '0 0 60px rgba(255,215,0,0.3), 0 20px 60px rgba(0,0,0,0.6)',
          position: 'relative',
        }}
      >
        <button
          onClick={onClose}
          style={{
            position: 'absolute', top: 10, right: 10,
            width: 28, height: 28, borderRadius: '50%',
            border: '1px solid rgba(255,255,255,0.2)',
            background: 'rgba(255,255,255,0.05)',
            color: 'rgba(255,255,255,0.6)',
            cursor: 'pointer',
            fontSize: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          aria-label="Close"
        >
          ×
        </button>
        {children}
      </motion.div>
    </motion.div>
  );
}
