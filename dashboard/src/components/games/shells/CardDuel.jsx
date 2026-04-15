'use client';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { play } from '@/lib/gameSounds';

/**
 * Card Duel — 1v1 style. Each student has a hero card with HP.
 * Correct answer = deal 10 damage to opponent (simulated client-side).
 * Wrong answer = take 10 damage.
 * First to 0 HP loses.
 *
 * Opponent is shown as a generic "RIVAL" card with simulated HP drop to
 * keep UX tight without bracket-pairing backend work.
 */
export default function CardDuel({
  question, view = 'student', onAnswer,
  questionIndex = 0, totalQuestions = 1, lastResult = null,
}) {
  const [selected, setSelected] = useState(null);
  const [myHp, setMyHp] = useState(100);
  const [rivalHp, setRivalHp] = useState(100);

  useEffect(() => { setSelected(null); }, [question?.question_text]);

  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) {
      play('correct');
      setRivalHp(h => Math.max(0, h - 25));
    } else {
      play('incorrect');
      setMyHp(h => Math.max(0, h - 20));
    }
  }, [lastResult]);

  const won = rivalHp <= 0 && myHp > 0;
  const lost = myHp <= 0;

  if (!question) return <Waiting />;

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(180deg, #1a0a2a 0%, #000 100%)',
      color: 'white', fontFamily: 'Nunito', padding: 24,
    }}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 28,
          textAlign: 'center', marginBottom: 24, color: '#FF8A6E',
          textShadow: '0 0 16px #D86C52' }}>
          ⚔ Card Duel
        </h1>

        {/* Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 24, alignItems: 'center', marginBottom: 32 }}>
          <HeroCard name="YOU" hp={myHp} color="#6BA08A" isMine />
          <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 32, color: '#FFD87A',
            textShadow: '0 0 12px #DAB04E' }}>VS</div>
          <HeroCard name="RIVAL" hp={rivalHp} color="#D86C52" flipped />
        </div>

        {won || lost ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{
              textAlign: 'center', padding: 40,
              background: won ? 'linear-gradient(135deg, #FFD87A, #DAB04E)' : 'linear-gradient(135deg, #7f1d1d, #3a0a0a)',
              color: won ? '#1a0a2a' : 'white',
              borderRadius: 20,
              fontFamily: "'DM Serif Display', serif",
              fontSize: 40,
            }}>
            {won ? '🏆 VICTORY!' : '☠ DEFEATED'}
          </motion.div>
        ) : (
          <>
            {/* Question */}
            <AnimatePresence mode="wait">
              <motion.div key={questionIndex}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                style={{
                  padding: 24, marginBottom: 20,
                  background: 'rgba(255,216,122,0.08)',
                  border: '2px solid #FFD87A',
                  borderRadius: 14,
                  textAlign: 'center',
                }}>
                <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 22, lineHeight: 1.3 }}>
                  {question.question_text}
                </h2>
              </motion.div>
            </AnimatePresence>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
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
                      padding: 14,
                      background: revealed && isCorrect ? 'linear-gradient(135deg, #16a34a, #0e8a3a)'
                        : revealed && isWrongSel ? 'linear-gradient(135deg, #ef4444, #7f1d1d)'
                        : isSel ? 'rgba(255,216,122,0.3)'
                        : 'rgba(255,255,255,0.08)',
                      border: `2px solid ${isSel ? '#FFD87A' : 'rgba(255,255,255,0.2)'}`,
                      color: 'white',
                      borderRadius: 10,
                      fontSize: 15, fontWeight: 700,
                      cursor: selected || view === 'teacher' ? 'default' : 'pointer',
                      textAlign: 'left',
                    }}>
                    {opt}
                  </motion.button>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function HeroCard({ name, hp, color, isMine, flipped }) {
  return (
    <motion.div
      animate={{ y: [0, -4, 0] }}
      transition={{ duration: 2, repeat: Infinity }}
      style={{
        padding: 20,
        background: `linear-gradient(135deg, ${color}, ${color}AA)`,
        border: `3px solid ${isMine ? 'white' : 'rgba(255,255,255,0.3)'}`,
        borderRadius: 16,
        boxShadow: isMine ? `0 0 24px ${color}` : 'none',
        minHeight: 180,
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        transform: flipped ? 'rotateY(0)' : 'rotateY(0)',
      }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 800, letterSpacing: 2, fontSize: 14 }}>{name}</span>
        <span style={{ fontSize: 14, fontWeight: 800 }}>HP {hp}/100</span>
      </div>
      <div style={{ fontSize: 50, textAlign: 'center', opacity: 0.6 }}>
        {isMine ? '🛡' : '⚔'}
      </div>
      {/* HP bar */}
      <div style={{ height: 12, borderRadius: 6, background: 'rgba(0,0,0,0.4)', overflow: 'hidden' }}>
        <motion.div
          animate={{ width: `${hp}%` }}
          transition={{ duration: 0.6, type: 'spring' }}
          style={{
            height: '100%',
            background: hp > 50 ? '#9ED4BC' : hp > 25 ? '#FFD87A' : '#FF8A6E',
          }}
        />
      </div>
    </motion.div>
  );
}

function Waiting() {
  return <div style={{ minHeight: '100vh',
    background: 'linear-gradient(180deg, #1a0a2a 0%, #000 100%)',
    color: '#FFD87A', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: 'Nunito', fontSize: 22 }}>Shuffling deck…</div>;
}
