'use client';
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Clock, CheckCircle, XCircle } from 'lucide-react';
import { play } from '@/lib/gameSounds';

/**
 * Speed Rush — rapid-fire sprint. Every student answers the same question pool
 * at their own pace (self-paced, teacher doesn't advance). First to complete
 * wins; accuracy is the tiebreaker.
 *
 * Implementation note: the teacher's Next button still advances question index
 * for everyone (synced), but the UI emphasizes personal completion + streak.
 * True self-pacing would require backend changes — scoped as follow-up.
 */
export default function SpeedRush({
  question, players = [], view = 'student', onAnswer,
  questionIndex = 0, totalQuestions = 1, lastResult = null,
}) {
  const [selected, setSelected] = useState(null);
  const [streak, setStreak] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const startedRef = useRef(null);

  useEffect(() => {
    setSelected(null);
    if (!startedRef.current) startedRef.current = Date.now();
  }, [question?.question_text]);

  useEffect(() => {
    const iv = setInterval(() => {
      if (startedRef.current) setElapsed(Math.floor((Date.now() - startedRef.current) / 1000));
    }, 100);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) { play('correct'); setStreak(s => s + 1); }
    else { play('incorrect'); setStreak(0); }
  }, [lastResult]);

  const progressPct = totalQuestions > 0 ? (questionIndex / totalQuestions) * 100 : 0;

  if (!question) return <Waiting />;

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a0a2a 0%, #0a0514 100%)',
      color: 'white',
      fontFamily: 'Nunito', padding: 24,
    }}>
      {/* Top HUD */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
        gap: 16, marginBottom: 24, maxWidth: 900, margin: '0 auto 24px',
      }}>
        <HudTile icon={Zap} label="STREAK" value={streak} color="#FFD700" />
        <HudTile icon={Clock} label="TIME" value={`${elapsed}s`} color="#00E5FF" />
        <HudTile label="Q" value={`${questionIndex + 1}/${totalQuestions}`} color="#FF6EC7" />
      </div>

      {/* Progress bar */}
      <div style={{ maxWidth: 900, margin: '0 auto 32px' }}>
        <div style={{
          height: 8, borderRadius: 4,
          background: 'rgba(255,255,255,0.1)',
          overflow: 'hidden',
        }}>
          <motion.div
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.5 }}
            style={{
              height: '100%',
              background: 'linear-gradient(90deg, #FFD700, #FF6EC7)',
              boxShadow: '0 0 10px #FF6EC7',
            }}
          />
        </div>
      </div>

      {/* Question */}
      <AnimatePresence mode="wait">
        <motion.div
          key={questionIndex}
          initial={{ opacity: 0, x: 100 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -100 }}
          transition={{ type: 'spring', stiffness: 260, damping: 22 }}
          style={{ maxWidth: 900, margin: '0 auto' }}>
          <h2 style={{
            fontSize: 32, fontWeight: 800, textAlign: 'center',
            marginBottom: 32, lineHeight: 1.2,
            textShadow: '0 0 20px rgba(255,110,199,0.5)',
          }}>
            {question.question_text}
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {(question.options || []).map((opt, i) => {
              const isSelected = selected === opt;
              const isCorrect = lastResult?.correct_answer === opt;
              const isWrongSelected = lastResult && isSelected && !lastResult.correct;
              const revealed = !!lastResult;
              const colors = ['#FF6EC7', '#00E5FF', '#FFD700', '#9D4EDD'];
              return (
                <motion.button
                  key={`${questionIndex}-${i}`}
                  initial={{ opacity: 0, y: 40 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 + i * 0.06 }}
                  whileHover={{ scale: revealed ? 1 : 1.03 }}
                  whileTap={{ scale: 0.96 }}
                  disabled={!!selected || view === 'teacher'}
                  onClick={() => { if (view === 'student') { setSelected(opt); onAnswer?.(opt); } }}
                  style={{
                    padding: 24,
                    background: revealed && isCorrect ? 'linear-gradient(135deg, #16a34a, #0e8a3a)'
                      : revealed && isWrongSelected ? 'linear-gradient(135deg, #ef4444, #b91c1c)'
                      : `linear-gradient(135deg, ${colors[i]}, ${colors[i]}CC)`,
                    color: 'white',
                    border: 'none',
                    borderRadius: 16,
                    fontSize: 18, fontWeight: 700,
                    cursor: !selected && view === 'student' ? 'pointer' : 'default',
                    textAlign: 'left',
                    boxShadow: `0 0 20px ${colors[i]}66`,
                    opacity: revealed && !isCorrect && !isWrongSelected ? 0.4 : 1,
                  }}>
                  {opt}
                  {revealed && isCorrect && <CheckCircle style={{ float: 'right', width: 22, height: 22 }} />}
                  {revealed && isWrongSelected && <XCircle style={{ float: 'right', width: 22, height: 22 }} />}
                </motion.button>
              );
            })}
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Teacher — player leaderboard overlay */}
      {view === 'teacher' && (
        <div style={{
          maxWidth: 900, margin: '32px auto 0',
          padding: 16,
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 12,
        }}>
          <h3 style={{ fontSize: 14, letterSpacing: 3, color: '#FFD700', marginBottom: 12 }}>
            LIVE RACE
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8 }}>
            {[...players].sort((a,b) => (b.score||0) - (a.score||0)).map(p => (
              <div key={p.player_id} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: 8,
                background: 'rgba(255,255,255,0.08)',
                borderRadius: 8,
              }}>
                <span style={{ fontSize: 22 }}>{p.avatar || '🐻'}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: '#FFD700' }}>{p.score || 0}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HudTile({ icon: Icon, label, value, color }) {
  return (
    <div style={{
      padding: 12,
      background: 'rgba(255,255,255,0.05)',
      border: `1px solid ${color}`,
      borderRadius: 12,
      display: 'flex', alignItems: 'center', gap: 10,
      boxShadow: `0 0 16px ${color}33`,
    }}>
      {Icon && <Icon style={{ width: 20, height: 20, color }} />}
      <div>
        <div style={{ fontSize: 10, letterSpacing: 2, color: 'rgba(255,255,255,0.6)' }}>{label}</div>
        <div style={{ fontSize: 22, fontWeight: 800, color }}>{value}</div>
      </div>
    </div>
  );
}

function Waiting() {
  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a0a2a 0%, #0a0514 100%)',
      color: '#FF6EC7',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Nunito', fontSize: 22, fontWeight: 700,
    }}>
      Ready…
    </div>
  );
}
