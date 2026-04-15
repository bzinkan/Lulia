'use client';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { play } from '@/lib/gameSounds';
import { correctAnswer } from '@/lib/confetti';

const CATEGORIES = ['Vocab', 'Facts', 'People', 'Events', 'Concepts', 'Applications'];
const WHEEL_COLORS = ['#FF8A6E', '#9ED4BC', '#FFD87A', '#A7C9E8', '#C5A8E8', '#4E8C96'];
const LETTERS = ['A', 'B', 'C', 'D'];

export default function WheelSpin({
  question, players = [], view = 'student', onAnswer,
  questionIndex = 0, totalQuestions = 1, lastResult = null,
}) {
  const [rotation, setRotation] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const [selected, setSelected] = useState(null);
  const [showWheel, setShowWheel] = useState(true);

  useEffect(() => {
    setSelected(null);
    setShowWheel(true);
  }, [question?.question_text]);

  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) { play('correct'); correctAnswer({ x: 0.5, y: 0.5 }); }
    else play('incorrect');
  }, [lastResult]);

  function spin() {
    if (spinning) return;
    setSpinning(true);
    const sliceIdx = questionIndex % CATEGORIES.length;
    const targetDeg = 360 * 5 + (360 - (sliceIdx * 60 + 30)); // land pointer on this slice
    setRotation(targetDeg);
    setTimeout(() => {
      setSpinning(false);
      setShowWheel(false);
      play('whoosh');
    }, 2800);
  }

  if (!question) return <Waiting />;

  return (
    <div style={{
      minHeight: '100vh',
      background: 'radial-gradient(ellipse at top, #3d1a4a 0%, #1a0a26 100%)',
      color: 'white', fontFamily: 'Nunito', padding: 24,
    }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 32, textAlign: 'center',
          color: '#FFD87A', textShadow: '0 0 16px #FFD87A', marginBottom: 24 }}>
          🎡 Wheel Spin
        </h1>

        <AnimatePresence mode="wait">
          {showWheel ? (
            <motion.div key="wheel"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.6 }}
              style={{ textAlign: 'center' }}>
              {/* Wheel */}
              <div style={{ position: 'relative', width: 360, height: 360, margin: '0 auto 24px' }}>
                {/* Pointer */}
                <div style={{
                  position: 'absolute', top: -12, left: '50%', transform: 'translateX(-50%)',
                  width: 0, height: 0,
                  borderLeft: '16px solid transparent',
                  borderRight: '16px solid transparent',
                  borderTop: '28px solid #FFD87A',
                  filter: 'drop-shadow(0 0 8px #FFD87A)',
                  zIndex: 2,
                }} />
                <motion.svg
                  viewBox="0 0 200 200"
                  width="360" height="360"
                  animate={{ rotate: rotation }}
                  transition={{ duration: 2.8, ease: [0.2, 0.8, 0.2, 1] }}>
                  {CATEGORIES.map((cat, i) => {
                    const a1 = (i * 60 - 90) * Math.PI / 180;
                    const a2 = ((i + 1) * 60 - 90) * Math.PI / 180;
                    const x1 = 100 + 90 * Math.cos(a1);
                    const y1 = 100 + 90 * Math.sin(a1);
                    const x2 = 100 + 90 * Math.cos(a2);
                    const y2 = 100 + 90 * Math.sin(a2);
                    // text position
                    const tA = (i * 60 + 30 - 90) * Math.PI / 180;
                    const tx = 100 + 55 * Math.cos(tA);
                    const ty = 100 + 55 * Math.sin(tA);
                    return (
                      <g key={i}>
                        <path d={`M100,100 L${x1},${y1} A90,90 0 0,1 ${x2},${y2} Z`}
                          fill={WHEEL_COLORS[i]} stroke="#1a0a26" strokeWidth="1.5" />
                        <text x={tx} y={ty}
                          fontFamily="Nunito" fontSize="10" fontWeight="bold"
                          fill="#1a0a26" textAnchor="middle" dominantBaseline="middle"
                          transform={`rotate(${i * 60 + 30} ${tx} ${ty})`}>
                          {cat.toUpperCase()}
                        </text>
                      </g>
                    );
                  })}
                  <circle cx="100" cy="100" r="12" fill="#FFD87A" stroke="#1a0a26" strokeWidth="2" />
                </motion.svg>
              </div>

              {view === 'student' && !spinning && (
                <button onClick={spin}
                  style={{
                    padding: '16px 48px',
                    background: 'linear-gradient(135deg, #FFD87A, #DAB04E)',
                    color: '#1a0a26',
                    border: 'none', borderRadius: 30,
                    fontSize: 20, fontWeight: 800,
                    cursor: 'pointer',
                    boxShadow: '0 6px 20px rgba(255,216,122,0.4)',
                  }}>
                  SPIN IT
                </button>
              )}
              {spinning && (
                <div style={{ fontSize: 18, color: '#FFD87A', letterSpacing: 3 }}>SPINNING…</div>
              )}
            </motion.div>
          ) : (
            <motion.div key="question"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{ textAlign: 'center' }}>
              <div style={{
                display: 'inline-block',
                padding: '6px 20px', marginBottom: 24,
                background: WHEEL_COLORS[questionIndex % CATEGORIES.length],
                color: '#1a0a26', borderRadius: 20,
                fontSize: 14, fontWeight: 800, letterSpacing: 2,
              }}>
                {CATEGORIES[questionIndex % CATEGORIES.length].toUpperCase()}
              </div>
              <h2 style={{
                fontFamily: "'DM Serif Display', serif",
                fontSize: 28, margin: '0 auto 28px',
                maxWidth: 700, lineHeight: 1.3,
              }}>
                {question.question_text}
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, maxWidth: 700, margin: '0 auto' }}>
                {(question.options || []).map((opt, i) => {
                  const isSel = selected === opt;
                  const isCorrect = lastResult?.correct_answer === opt;
                  const isWrongSel = lastResult && isSel && !lastResult.correct;
                  const revealed = !!lastResult;
                  return (
                    <button key={i}
                      disabled={!!selected || view === 'teacher'}
                      onClick={() => { if (view === 'student') { setSelected(opt); onAnswer?.(opt); } }}
                      style={{
                        padding: 18,
                        background: revealed && isCorrect ? 'linear-gradient(135deg, #16a34a, #0e8a3a)'
                          : revealed && isWrongSel ? 'linear-gradient(135deg, #ef4444, #b91c1c)'
                          : isSel ? 'rgba(255,216,122,0.25)'
                          : 'rgba(255,255,255,0.08)',
                        border: `2px solid ${isSel || revealed ? '#FFD87A' : 'rgba(255,255,255,0.2)'}`,
                        color: 'white',
                        borderRadius: 12,
                        fontSize: 16, fontWeight: 700,
                        cursor: selected || view === 'teacher' ? 'default' : 'pointer',
                        textAlign: 'left',
                      }}>
                      <strong style={{ color: '#FFD87A', marginRight: 10 }}>{LETTERS[i]}.</strong>
                      {opt}
                    </button>
                  );
                })}
              </div>
              {view === 'teacher' && (
                <p style={{ marginTop: 16, fontSize: 13, color: '#FFD87A' }}>
                  Correct: <strong>{question.answer}</strong>
                </p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function Waiting() {
  return <div style={{ minHeight: '100vh',
    background: 'radial-gradient(ellipse at top, #3d1a4a 0%, #1a0a26 100%)',
    color: '#FFD87A', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: 'Nunito', fontSize: 22 }}>Spinning up…</div>;
}
