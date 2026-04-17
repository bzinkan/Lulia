'use client';
import { useEffect, useMemo, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Scroll, MapPin, BookOpen, Award } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer, winnerCelebration } from '@/lib/confetti';
import { ArcadeChip } from '@/components/games/CabinetStage';

/**
 * History Quest — arcade-cabinet edition (v1 April 2026). NEW SHELL.
 *
 * Parchment gold #B48838 accent from registry. Aged-paper aesthetic with
 * quill-ink typography on the dark arcade stage. Events appear one at a time;
 * student picks the correct answer from MCQ options — framed as choosing the
 * right era/date/fact for each historical event.
 *
 * Renders inside CabinetStage. Interior content only — no full-page bg.
 *
 * Visual features:
 *   - Parchment scroll event card with aged paper gradient + wax seal motif
 *   - Timeline progress rail showing placed events as ink dots
 *   - Fact scroll unfurl on correct answer — reveals the full answer with
 *     a decorative scroll frame animation
 *   - Wrong answer: red seal "stamp" + correct answer reveal
 *   - Streak tracks consecutive correct → "Scholar" / "Historian" / "Sage"
 *   - Teacher view: question + answer display + ranked student leaderboard
 *
 * Server contract: standard MCQ — question.question_text, question.options[],
 * question.answer. onAnswer(selected_option) fires on tap.
 */

// Scholar streak tiers
const SCHOLAR_TIERS = [
  { min: 0,  label: 'APPRENTICE', mult: 1,   icon: '📜' },
  { min: 3,  label: 'SCHOLAR',    mult: 1.5, icon: '🎓' },
  { min: 6,  label: 'HISTORIAN',  mult: 2,   icon: '📚' },
  { min: 10, label: 'SAGE',       mult: 3,   icon: '🏛' },
];
function getScholarTier(streak) {
  for (let i = SCHOLAR_TIERS.length - 1; i >= 0; i--) {
    if (streak >= SCHOLAR_TIERS[i].min) return SCHOLAR_TIERS[i];
  }
  return SCHOLAR_TIERS[0];
}
function nextScholarAt(streak) {
  for (const t of SCHOLAR_TIERS) { if (t.min > streak) return t.min; }
  return null;
}

// MCQ option letter labels
const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];
const OPTION_ACCENTS = ['#B48838', '#8B6914', '#C9A84C', '#7A5A1E', '#D4B96A', '#6B4C12'];

export default function HistoryQuest({
  allQuestions = [], question, players = [], view = 'student',
  onAnswer, config = {},
  questionIndex = 0, totalQuestions = 15, lastResult = null, playerId = null,
}) {
  const [selected, setSelected] = useState(null);
  const [locked, setLocked] = useState(false);
  const [showScroll, setShowScroll] = useState(false);   // fact scroll unfurl
  const [showResult, setShowResult] = useState(null);     // 'correct' | 'wrong'
  const [correctText, setCorrectText] = useState('');
  const [streak, setStreak] = useState(0);
  const [bestStreak, setBestStreak] = useState(0);
  const [score, setScore] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [wrongCount, setWrongCount] = useState(0);
  const [placedEvents, setPlacedEvents] = useState([]);   // timeline dots
  const [gameOver, setGameOver] = useState(false);

  const options = question?.options || [];
  const tier = getScholarTier(streak);

  // Reset per-question state
  useEffect(() => {
    setSelected(null);
    setLocked(false);
    setShowScroll(false);
    setShowResult(null);
    setCorrectText('');
  }, [question?.question_text]);

  // Handle result
  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) {
      play('correct');
      correctAnswer({ x: 0.5, y: 0.45 });
      setShowResult('correct');
      setShowScroll(true);
      setStreak(s => s + 1);
      setBestStreak(b => Math.max(b, streak + 1));
      setCorrectCount(c => c + 1);
      const t = getScholarTier(streak + 1);
      setScore(s => s + Math.round(100 * t.mult));
      setPlacedEvents(prev => [...prev, {
        index: questionIndex,
        text: question?.question_text?.substring(0, 30) || '?',
        correct: true,
      }]);
    } else {
      play('incorrect');
      setShowResult('wrong');
      setCorrectText(lastResult.correct_answer || question?.answer || '?');
      setStreak(0);
      setWrongCount(w => w + 1);
      setPlacedEvents(prev => [...prev, {
        index: questionIndex,
        text: question?.question_text?.substring(0, 30) || '?',
        correct: false,
      }]);
    }
    const t = setTimeout(() => {
      setShowResult(null);
      setShowScroll(false);
    }, 2200);
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
      }, 2400);
    }
  }, [questionIndex, totalQuestions, lastResult, gameOver]);

  const handleSelect = useCallback((opt) => {
    if (locked || showResult) return;
    setSelected(opt);
    setLocked(true);
    play('whoosh');
    // Brief suspense then submit
    setTimeout(() => { onAnswer?.(opt); }, 400);
  }, [locked, showResult, onAnswer]);

  // HUD
  const hudLeft = (
    <>
      <ArcadeChip>EVENT {questionIndex + 1}/{totalQuestions}</ArcadeChip>
      <ArcadeChip variant="ghost">{tier.icon} {tier.label}</ArcadeChip>
    </>
  );
  const hudRight = (
    <>
      <ArcadeChip variant={streak >= 3 ? 'solid' : 'ghost'}>
        STREAK {streak} ×{tier.mult}
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
            background: 'linear-gradient(180deg, rgba(180,136,56,0.18), rgba(10,10,24,0.85))',
            border: '2px solid var(--arcade-accent, #B48838)',
            borderRadius: 18,
            boxShadow: '0 0 40px color-mix(in srgb, var(--arcade-accent, #B48838) 35%, transparent)',
          }}
        >
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 12,
            letterSpacing: 2.5, color: 'var(--arcade-accent, #B48838)', marginBottom: 12,
          }}>
            {correctCount >= totalQuestions * 0.9 ? '★ MASTER HISTORIAN ★' : '★ QUEST COMPLETE ★'}
          </div>
          <div style={{
            fontFamily: "'Press Start 2P', monospace", fontSize: 26,
            letterSpacing: 2, color: '#D4B96A', marginBottom: 16,
            textShadow: '0 0 18px rgba(212,185,106,0.6)',
          }}>
            {score} PTS
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
            <WinStat label="CORRECT" value={`${correctCount}/${totalQuestions}`} accent="#D4B96A" />
            <WinStat label="BEST STREAK" value={bestStreak} accent="#D4B96A" />
            <WinStat label="RANK" value={getScholarTier(bestStreak).label} accent="#D4B96A" />
          </div>
          {/* Mini timeline of placed events */}
          <div style={{ marginTop: 20 }}>
            <TimelineRail events={placedEvents} total={totalQuestions} />
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

        {/* Timeline progress rail */}
        <TimelineRail events={placedEvents} total={totalQuestions} />

        {/* Parchment scroll event card */}
        <div style={{
          maxWidth: 720, margin: '16px auto',
          position: 'relative',
        }}>
          {/* Streak tier banner */}
          <AnimatePresence>
            {streak >= 3 && (
              <motion.div
                initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{
                  textAlign: 'center', marginBottom: 8,
                  fontFamily: "'Press Start 2P', monospace",
                  fontSize: 10, letterSpacing: 2.5,
                  color: '#D4B96A',
                }}
              >
                {tier.icon} {tier.label} ×{tier.mult} {tier.icon}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Event scroll card */}
          <motion.div
            key={question?.question_text || questionIndex}
            initial={{ opacity: 0, y: 16, rotateX: -5 }}
            animate={{ opacity: 1, y: 0, rotateX: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 18 }}
            style={{
              padding: '28px 24px',
              borderRadius: 16,
              background: `
                radial-gradient(circle at 50% -10%, rgba(212,185,106,0.15), transparent 55%),
                linear-gradient(180deg, #1A1520 0%, #0F0D16 100%)`,
              border: '2px solid color-mix(in srgb, var(--arcade-accent, #B48838) 60%, transparent)',
              boxShadow: `
                0 0 24px color-mix(in srgb, var(--arcade-accent, #B48838) 20%, transparent),
                0 12px 40px rgba(0,0,0,0.55)`,
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {/* Parchment texture overlay */}
            <div style={{
              position: 'absolute', inset: 0, opacity: 0.04, pointerEvents: 'none',
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='4' height='4'%3E%3Crect width='1' height='1' fill='%23B48838'/%3E%3C/svg%3E")`,
              backgroundSize: '4px 4px',
            }} />

            {/* Scroll icon + event label */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
            }}>
              <Scroll style={{ width: 16, height: 16, color: '#B48838' }} />
              <span style={{
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 9, letterSpacing: 2, color: '#B48838',
              }}>
                EVENT {questionIndex + 1}
              </span>
            </div>

            {/* Question text */}
            <div style={{
              fontFamily: 'Space Grotesk, sans-serif',
              fontWeight: 700, fontSize: 'clamp(22px, 4vw, 32px)',
              lineHeight: 1.25,
              color: '#F0E6D0',
              textShadow: '0 0 12px rgba(212,185,106,0.2)',
              marginBottom: 20,
              position: 'relative', zIndex: 1,
            }}>
              {question?.question_text || 'Loading event...'}
            </div>

            {/* Answer options */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: options.length <= 2 ? '1fr' : 'repeat(2, 1fr)',
              gap: 10,
              position: 'relative', zIndex: 1,
            }}>
              {options.map((opt, i) => {
                const isSelected = selected === opt;
                const isCorrectOpt = showResult && opt === (question?.answer || '');
                const isWrongSel = showResult === 'wrong' && isSelected;
                const isDisabled = locked || !!showResult;

                let bg = `linear-gradient(180deg,
                  color-mix(in srgb, ${OPTION_ACCENTS[i % OPTION_ACCENTS.length]} 85%, white 15%) 0%,
                  ${OPTION_ACCENTS[i % OPTION_ACCENTS.length]} 45%,
                  color-mix(in srgb, ${OPTION_ACCENTS[i % OPTION_ACCENTS.length]} 70%, black 30%) 100%)`;
                if (isCorrectOpt) bg = 'linear-gradient(180deg, #1DB954 0%, #168D40 100%)';
                if (isWrongSel) bg = 'linear-gradient(180deg, #FF3864 0%, #CC2040 100%)';

                return (
                  <motion.button
                    key={opt}
                    onClick={() => handleSelect(opt)}
                    disabled={isDisabled}
                    whileHover={!isDisabled ? { scale: 1.02, y: -1 } : {}}
                    whileTap={!isDisabled ? { scale: 0.97 } : {}}
                    animate={
                      isWrongSel ? { x: [-2, 2, -2, 2, 0] }
                      : isCorrectOpt ? { scale: [1, 1.04, 1] }
                      : {}
                    }
                    transition={{ duration: 0.35 }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '14px 16px',
                      borderRadius: 12,
                      background: bg,
                      color: '#0A0A18',
                      fontFamily: 'Space Grotesk, sans-serif',
                      fontWeight: 700, fontSize: 14,
                      textAlign: 'left',
                      cursor: isDisabled ? 'default' : 'pointer',
                      border: isSelected && !showResult
                        ? '2px solid rgba(255,255,255,0.9)'
                        : '2px solid transparent',
                      boxShadow: isSelected && !showResult
                        ? '0 0 16px rgba(255,255,255,0.3)'
                        : '0 4px 0 rgba(0,0,0,0.3), 0 6px 14px rgba(0,0,0,0.4)',
                      opacity: isDisabled && !isSelected && !isCorrectOpt ? 0.5 : 1,
                      transition: 'opacity 0.2s',
                    }}
                  >
                    <span style={{
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 11, minWidth: 22,
                      color: 'rgba(10,10,24,0.6)',
                    }}>
                      {LETTERS[i]}
                    </span>
                    <span style={{ flex: 1, lineHeight: 1.3 }}>{opt}</span>
                    {isCorrectOpt && <BookOpen style={{ width: 16, height: 16, color: '#0A3A18' }} />}
                  </motion.button>
                );
              })}
            </div>

            {/* Fact scroll unfurl on correct */}
            <AnimatePresence>
              {showScroll && showResult === 'correct' && (
                <motion.div
                  initial={{ opacity: 0, height: 0, marginTop: 0 }}
                  animate={{ opacity: 1, height: 'auto', marginTop: 16 }}
                  exit={{ opacity: 0, height: 0, marginTop: 0 }}
                  transition={{ duration: 0.4, type: 'spring', stiffness: 180 }}
                  style={{ overflow: 'hidden', position: 'relative', zIndex: 1 }}
                >
                  <div style={{
                    padding: '14px 18px',
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, rgba(212,185,106,0.12), rgba(10,10,24,0.75))',
                    border: '1px solid rgba(212,185,106,0.35)',
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                  }}>
                    <Scroll style={{ width: 18, height: 18, color: '#D4B96A', flexShrink: 0, marginTop: 2 }} />
                    <div>
                      <div style={{
                        fontFamily: "'Press Start 2P', monospace",
                        fontSize: 8, letterSpacing: 2, color: '#D4B96A', marginBottom: 4,
                      }}>
                        SCROLL UNLOCKED
                      </div>
                      <div style={{
                        fontFamily: 'Space Grotesk, sans-serif',
                        fontSize: 13, color: 'rgba(240,230,208,0.9)', lineHeight: 1.4,
                      }}>
                        Correct! The answer is <strong style={{ color: '#D4B96A' }}>{question?.answer}</strong>.
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Wrong answer reveal */}
            <AnimatePresence>
              {showResult === 'wrong' && correctText && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  style={{
                    marginTop: 14, textAlign: 'center',
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 10, letterSpacing: 1.5,
                    color: '#FF3864',
                    position: 'relative', zIndex: 1,
                  }}
                >
                  ✗ CORRECT ANSWER: {correctText}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* Streak hint */}
          {streak >= 1 && streak < 10 && (
            <div style={{
              textAlign: 'center', marginTop: 12,
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 9, letterSpacing: 2,
              color: streak >= 3 ? '#D4B96A' : 'rgba(247,247,255,0.45)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>
              <Award style={{ width: 12, height: 12 }} />
              STREAK {streak} {nextScholarAt(streak) ? `— NEXT RANK AT ${nextScholarAt(streak)}` : ''}
            </div>
          )}
        </div>
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
        placedEvents={placedEvents}
      />
    </div>
  );
}

// ============================================================
//             TimelineRail — horizontal event progress
// ============================================================

function TimelineRail({ events = [], total }) {
  return (
    <div style={{
      maxWidth: 720, margin: '0 auto 8px',
      padding: '10px 16px',
      borderRadius: 10,
      background: 'linear-gradient(180deg, rgba(10,10,24,0.6), rgba(10,10,24,0.4))',
      border: '1px solid rgba(180,136,56,0.2)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 0,
        position: 'relative', height: 24,
      }}>
        {/* Rail line */}
        <div style={{
          position: 'absolute', left: 0, right: 0, top: '50%', height: 2,
          background: 'rgba(180,136,56,0.3)', transform: 'translateY(-50%)',
        }} />
        {/* Fill line for placed events */}
        <div style={{
          position: 'absolute', left: 0, top: '50%', height: 2,
          width: total > 0 ? `${(events.length / total) * 100}%` : '0%',
          background: 'linear-gradient(90deg, #B48838, #D4B96A)',
          transform: 'translateY(-50%)',
          transition: 'width 0.4s ease',
          boxShadow: '0 0 8px rgba(180,136,56,0.5)',
        }} />
        {/* Dots */}
        {Array.from({ length: total }).map((_, i) => {
          const event = events.find(e => e.index === i);
          const isPlaced = !!event;
          const dotColor = event?.correct ? '#D4B96A' : event ? '#FF3864' : 'rgba(180,136,56,0.2)';
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: total > 1 ? `${(i / (total - 1)) * 100}%` : '50%',
                top: '50%',
                transform: 'translate(-50%, -50%)',
                width: isPlaced ? 10 : 6,
                height: isPlaced ? 10 : 6,
                borderRadius: '50%',
                background: dotColor,
                border: isPlaced ? '1.5px solid rgba(255,255,255,0.4)' : 'none',
                boxShadow: isPlaced && event.correct ? '0 0 8px rgba(212,185,106,0.6)' : 'none',
                transition: 'all 0.3s',
                zIndex: 1,
              }}
              title={event ? `${event.text}${event.correct ? ' ✓' : ' ✗'}` : `Event ${i + 1}`}
            />
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
//               TeacherBoard — question + leaderboard
// ============================================================

function TeacherBoard({ question, questionIndex, totalQuestions, players, placedEvents }) {
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
      {/* Current event display */}
      <div style={{
        padding: '20px 24px', marginBottom: 16,
        borderRadius: 14, textAlign: 'center',
        background: `
          radial-gradient(circle at 50% 0%, rgba(180,136,56,0.12), transparent 55%),
          linear-gradient(180deg, #0F0F24, #0A0A1A)`,
        border: '2px solid var(--arcade-accent, #B48838)',
        boxShadow: '0 0 24px rgba(180,136,56,0.2)',
      }}>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2, color: 'var(--arcade-ink-dim, #B6B7D8)',
          marginBottom: 8,
        }}>
          EVENT {questionIndex + 1} OF {totalQuestions}
        </div>
        <div style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 24, fontWeight: 700,
          color: '#F0E6D0',
          textShadow: '0 0 10px rgba(212,185,106,0.2)',
        }}>
          {question?.question_text || 'Waiting...'}
        </div>
        {question?.answer && (
          <div style={{
            marginTop: 8,
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 12, color: '#D4B96A',
          }}>
            → {question.answer}
          </div>
        )}
      </div>

      {/* Timeline */}
      <TimelineRail events={placedEvents} total={totalQuestions} />

      {/* Leaderboard */}
      <div style={{
        padding: '16px 18px', marginTop: 12,
        borderRadius: 14,
        background: 'linear-gradient(180deg, rgba(10,10,24,0.75), rgba(10,10,24,0.55))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{
          fontFamily: "'Press Start 2P', monospace",
          fontSize: 10, letterSpacing: 2,
          color: 'var(--arcade-accent, #B48838)', marginBottom: 12,
        }}>
          QUEST LOG · {rows.length} PLAYER{rows.length === 1 ? '' : 'S'}
        </div>
        {rows.length === 0 ? (
          <div style={{ fontSize: 13, color: 'rgba(247,247,255,0.55)' }}>
            Waiting for students to answer…
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rows.map((r, idx) => {
              const t = getScholarTier(r.streak);
              return (
                <div
                  key={r.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 14px', borderRadius: 10,
                    background: idx === 0
                      ? 'linear-gradient(90deg, rgba(180,136,56,0.12), rgba(10,10,24,0.7))'
                      : 'rgba(10,10,24,0.6)',
                    border: `1px solid ${idx === 0 ? 'rgba(180,136,56,0.35)' : 'rgba(255,255,255,0.06)'}`,
                  }}
                >
                  <div style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 14, color: idx === 0 ? '#D4B96A' : 'rgba(247,247,255,0.45)',
                    minWidth: 30,
                  }}>
                    {idx + 1}.
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontFamily: 'Space Grotesk, sans-serif',
                      fontSize: 14, fontWeight: 700,
                      color: idx === 0 ? '#D4B96A' : 'rgba(247,247,255,0.85)',
                    }}>
                      {r.name}
                    </div>
                    <div style={{
                      fontFamily: "'Press Start 2P', monospace",
                      fontSize: 8, letterSpacing: 1.5,
                      color: 'rgba(247,247,255,0.5)', marginTop: 2,
                    }}>
                      {t.icon} {t.label}{r.streak >= 3 ? ` · STREAK ${r.streak}` : ''}
                    </div>
                  </div>
                  <div style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 14, color: idx === 0 ? '#D4B96A' : 'var(--arcade-ink, #F7F7FF)',
                  }}>
                    {r.score}
                  </div>
                  <div style={{
                    fontFamily: "'Press Start 2P', monospace",
                    fontSize: 9, color: 'rgba(247,247,255,0.5)',
                    minWidth: 40, textAlign: 'right',
                  }}>
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
//                   StageHudBand
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
//                    WinStat helper
// ============================================================

function WinStat({ label, value, accent = '#D4B96A' }) {
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
        fontFamily: "'Press Start 2P', monospace", fontSize: 14, color: accent,
      }}>
        {value}
      </div>
    </div>
  );
}
