'use client';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Skull, Crosshair, Users } from 'lucide-react';
import { play } from '@/lib/gameSounds';

/**
 * Battle Royale — wrong answer eliminates. Last standing wins.
 * Student tracks their own lives client-side (starts at 1 by default;
 * config can extend to 2 or 3 strikes). Once eliminated they become
 * a spectator.
 */
export default function BattleRoyale({
  question, players = [], view = 'student', onAnswer, config = {},
  questionIndex = 0, totalQuestions = 1, lastResult = null,
}) {
  const maxStrikes = config.strikes || 1;
  const [selected, setSelected] = useState(null);
  const [strikes, setStrikes] = useState(0);
  const [eliminated, setEliminated] = useState(false);

  useEffect(() => { setSelected(null); }, [question?.question_text]);

  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) {
      play('correct');
    } else {
      play('incorrect');
      const nextStrikes = strikes + 1;
      setStrikes(nextStrikes);
      if (nextStrikes >= maxStrikes) setEliminated(true);
    }
  }, [lastResult]);

  if (!question) return <Waiting />;

  const aliveCount = Math.max(1, players.filter(p => (p.score || 0) >= 0).length);

  return (
    <div style={{
      minHeight: '100vh',
      background: eliminated
        ? 'linear-gradient(180deg, #1a0a0a 0%, #000 100%)'
        : 'linear-gradient(180deg, #3a1a0f 0%, #1a0a0a 100%)',
      color: 'white', fontFamily: 'Nunito', padding: 24,
    }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        {/* HUD */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8,
            padding: '6px 14px', background: 'rgba(239,68,68,0.15)',
            border: '1px solid #EF4444', borderRadius: 8 }}>
            <Users style={{ width: 18, height: 18, color: '#EF4444' }} />
            <span style={{ fontWeight: 800, color: '#EF4444' }}>{aliveCount} ALIVE</span>
          </div>
          <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 26,
            color: '#FF8A6E', textShadow: '0 0 12px #D86C52' }}>
            Battle Royale
          </h1>
          <div style={{ display: 'flex', gap: 4 }}>
            {Array.from({ length: maxStrikes }).map((_, i) => (
              <Skull key={i} style={{
                width: 22, height: 22,
                color: i < strikes ? '#EF4444' : 'rgba(255,255,255,0.2)',
                filter: i < strikes ? 'drop-shadow(0 0 6px #EF4444)' : 'none',
              }} />
            ))}
          </div>
        </div>

        {eliminated ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{
              textAlign: 'center', padding: '60px 24px',
              background: 'rgba(239,68,68,0.1)',
              border: '2px solid #EF4444', borderRadius: 20,
            }}>
            <Skull style={{ width: 80, height: 80, color: '#EF4444', margin: '0 auto 16px' }} />
            <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 40, color: '#FF8A6E' }}>
              ELIMINATED
            </h2>
            <p style={{ marginTop: 8, opacity: 0.7 }}>
              You&apos;re out. Watch the survivors battle it out.
            </p>
          </motion.div>
        ) : (
          <>
            {/* Question */}
            <AnimatePresence mode="wait">
              <motion.div key={questionIndex}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                style={{
                  background: 'linear-gradient(135deg, rgba(216,108,82,0.15), rgba(58,26,15,0.8))',
                  border: '2px solid #D86C52',
                  borderRadius: 12,
                  padding: '28px 24px',
                  marginBottom: 20,
                  textAlign: 'center',
                  boxShadow: '0 0 30px rgba(216,108,82,0.3)',
                }}>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
                  <Crosshair style={{ width: 22, height: 22, color: '#FF8A6E' }} />
                </div>
                <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 24, lineHeight: 1.3 }}>
                  {question.question_text}
                </h2>
              </motion.div>
            </AnimatePresence>

            {/* Answers */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {(question.options || []).map((opt, i) => {
                const isSel = selected === opt;
                const isCorrect = lastResult?.correct_answer === opt;
                const isWrongSel = lastResult && isSel && !lastResult.correct;
                const revealed = !!lastResult;
                return (
                  <motion.button key={i}
                    whileHover={{ scale: revealed ? 1 : 1.02 }}
                    whileTap={{ scale: 0.97 }}
                    disabled={!!selected || view === 'teacher'}
                    onClick={() => { if (view === 'student') { setSelected(opt); onAnswer?.(opt); } }}
                    style={{
                      padding: 18,
                      background: revealed && isCorrect ? 'linear-gradient(135deg, #16a34a, #0e8a3a)'
                        : revealed && isWrongSel ? 'linear-gradient(135deg, #ef4444, #7f1d1d)'
                        : isSel ? '#D86C52'
                        : 'rgba(255,255,255,0.08)',
                      border: `2px solid ${isSel || revealed ? '#D86C52' : 'rgba(255,255,255,0.2)'}`,
                      color: 'white',
                      borderRadius: 10,
                      fontSize: 16, fontWeight: 700,
                      cursor: selected || view === 'teacher' ? 'default' : 'pointer',
                      textAlign: 'left',
                      opacity: revealed && !isCorrect && !isWrongSel ? 0.4 : 1,
                    }}>
                    {opt}
                  </motion.button>
                );
              })}
            </div>

            {view === 'teacher' && (
              <div style={{ marginTop: 20, padding: 12,
                background: 'rgba(216,108,82,0.1)', border: '1px solid #D86C52',
                borderRadius: 8, textAlign: 'center', fontSize: 13, color: '#FF8A6E' }}>
                Answer: <strong>{question.answer}</strong>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Waiting() {
  return <div style={{ minHeight: '100vh',
    background: 'linear-gradient(180deg, #3a1a0f 0%, #1a0a0a 100%)',
    color: '#FF8A6E', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: 'Nunito', fontSize: 22 }}>Loading battle…</div>;
}
