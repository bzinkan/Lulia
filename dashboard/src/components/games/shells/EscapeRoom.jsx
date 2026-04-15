'use client';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Key, Lock, Unlock } from 'lucide-react';
import { play } from '@/lib/gameSounds';

/**
 * Escape Room — cooperative. Each question = a "room" that the class
 * must unlock. Progress shown as a chain of rooms; current room is the
 * active question. When the game ends (all rooms unlocked) → escape.
 */
export default function EscapeRoom({
  question, view = 'student', onAnswer,
  questionIndex = 0, totalQuestions = 1, lastResult = null,
}) {
  const [selected, setSelected] = useState(null);
  const rooms = Math.min(totalQuestions, 5);

  useEffect(() => { setSelected(null); }, [question?.question_text]);

  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) play('correct');
    else play('incorrect');
  }, [lastResult]);

  if (!question) return <Waiting />;

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(180deg, #0a1a2a 0%, #050f1a 100%)',
      color: 'white', fontFamily: 'Nunito', padding: 24,
    }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 28,
          textAlign: 'center', marginBottom: 16, color: '#A7C9E8',
          textShadow: '0 0 16px #6B9BC7' }}>
          🔐 Escape Room
        </h1>

        {/* Room chain */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginBottom: 32, alignItems: 'center' }}>
          {Array.from({ length: rooms }).map((_, i) => {
            const unlocked = i < questionIndex;
            const active = i === questionIndex;
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <motion.div
                  animate={active ? { scale: [1, 1.1, 1] } : {}}
                  transition={{ duration: 1.5, repeat: Infinity }}
                  style={{
                    width: 60, height: 60,
                    borderRadius: 12,
                    background: unlocked ? 'linear-gradient(135deg, #9ED4BC, #6BA08A)'
                      : active ? 'linear-gradient(135deg, #FFD87A, #DAB04E)'
                      : 'rgba(255,255,255,0.1)',
                    border: `2px solid ${active ? '#FFD87A' : unlocked ? '#6BA08A' : 'rgba(255,255,255,0.2)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: active ? '0 0 20px #FFD87A' : 'none',
                  }}>
                  {unlocked ? <Unlock style={{ width: 26, height: 26, color: '#1a1416' }} />
                    : active ? <Key style={{ width: 26, height: 26, color: '#1a1416' }} />
                    : <Lock style={{ width: 26, height: 26, color: 'rgba(255,255,255,0.3)' }} />}
                </motion.div>
                {i < rooms - 1 && (
                  <div style={{
                    width: 20, height: 2,
                    background: unlocked ? '#9ED4BC' : 'rgba(255,255,255,0.15)',
                  }} />
                )}
              </div>
            );
          })}
        </div>

        {/* Question (the puzzle for current room) */}
        <AnimatePresence mode="wait">
          <motion.div key={questionIndex}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            style={{
              padding: 28,
              background: 'linear-gradient(135deg, rgba(167,201,232,0.12), rgba(10,26,42,0.8))',
              border: '2px solid #A7C9E8',
              borderRadius: 14,
              marginBottom: 20,
              boxShadow: '0 0 30px rgba(167,201,232,0.2)',
            }}>
            <div style={{ fontSize: 11, letterSpacing: 3, color: '#A7C9E8', marginBottom: 8 }}>
              ROOM {questionIndex + 1} — PUZZLE
            </div>
            <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 24, lineHeight: 1.3 }}>
              {question.question_text}
            </h2>
          </motion.div>
        </AnimatePresence>

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
                  padding: 16,
                  background: revealed && isCorrect ? 'linear-gradient(135deg, #16a34a, #0e8a3a)'
                    : revealed && isWrongSel ? 'linear-gradient(135deg, #ef4444, #7f1d1d)'
                    : isSel ? '#A7C9E8' + '44'
                    : 'rgba(255,255,255,0.06)',
                  border: `2px solid ${isSel ? '#A7C9E8' : 'rgba(167,201,232,0.25)'}`,
                  color: 'white', borderRadius: 10,
                  fontSize: 15, fontWeight: 700,
                  cursor: selected || view === 'teacher' ? 'default' : 'pointer',
                  textAlign: 'left',
                }}>
                {opt}
              </motion.button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function Waiting() {
  return <div style={{ minHeight: '100vh',
    background: 'linear-gradient(180deg, #0a1a2a 0%, #050f1a 100%)',
    color: '#A7C9E8', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: 'Nunito', fontSize: 22 }}>Locking doors…</div>;
}
