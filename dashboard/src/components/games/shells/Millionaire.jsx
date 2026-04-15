'use client';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import { play } from '@/lib/gameSounds';
import { correctAnswer } from '@/lib/confetti';

// 15-tier prize ladder — real Millionaire amounts
const LADDER = [
  '$100','$200','$300','$500','$1,000','$2,000','$4,000','$8,000',
  '$16,000','$32,000','$64,000','$125,000','$250,000','$500,000','$1 MILLION',
];
const SAFE_TIERS = [4, 9]; // $1,000 and $32,000

const LETTERS = ['A','B','C','D'];

export default function Millionaire({
  question, players = [], view = 'student', onAnswer, config = {},
  questionIndex = 0, totalQuestions = 15, lastResult = null,
}) {
  const [selected, setSelected] = useState(null);
  const [fiftyFiftyUsed, setFiftyFiftyUsed] = useState(false);
  const [fiftyFiftyHidden, setFiftyFiftyHidden] = useState(new Set());
  const [audienceUsed, setAudienceUsed] = useState(false);
  const [skipUsed, setSkipUsed] = useState(false);

  useEffect(() => {
    setSelected(null);
    setFiftyFiftyHidden(new Set());
  }, [question?.question_text]);

  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) { play('correct'); correctAnswer({ x: 0.5, y: 0.55 }); }
    else play('incorrect');
  }, [lastResult]);

  function useFiftyFifty() {
    if (fiftyFiftyUsed || !question) return;
    const wrongs = (question.options || []).filter(o => o !== question.answer);
    const hide = new Set();
    while (hide.size < 2 && wrongs.length > hide.size) {
      hide.add(wrongs[Math.floor(Math.random() * wrongs.length)]);
    }
    setFiftyFiftyHidden(hide);
    setFiftyFiftyUsed(true);
  }

  if (!question) {
    return <Waiting text="Next question loading…" />;
  }

  const currentTier = Math.min(questionIndex, 14);

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 20, color: 'white',
      fontFamily: "'DM Serif Display', serif",
      background: 'radial-gradient(ellipse at top, #001d3a 0%, #000714 100%)',
      minHeight: '100vh' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 32 }}>
        {/* LEFT — question + answers */}
        <div>
          <div style={{ textAlign: 'center', marginBottom: 12 }}>
            <span style={{ fontFamily: 'Nunito', fontSize: 12, letterSpacing: 4,
              color: '#FFD700', textShadow: '0 0 8px #FFD700' }}>
              FOR {LADDER[currentTier]}
            </span>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={questionIndex}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ type: 'spring', stiffness: 200, damping: 22 }}
              style={{
                background: 'linear-gradient(180deg, #0a2c5a, #001d3a)',
                border: '3px solid #FFD700',
                borderRadius: 12,
                padding: '32px 28px',
                textAlign: 'center',
                boxShadow: '0 0 40px rgba(255,215,0,0.3)',
                marginBottom: 24,
              }}>
              <h2 style={{ fontSize: 26, lineHeight: 1.3, fontWeight: 400 }}>
                {question.question_text}
              </h2>
            </motion.div>
          </AnimatePresence>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {(question.options || []).map((opt, i) => {
              const isHidden = fiftyFiftyHidden.has(opt);
              const isSelected = selected === opt;
              const isCorrect = lastResult?.correct_answer === opt;
              const isWrongSelected = lastResult && isSelected && !lastResult.correct;
              const revealed = !!lastResult;
              return (
                <motion.button
                  key={`${questionIndex}-${i}`}
                  initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
                  animate={{ opacity: isHidden ? 0.15 : 1, x: 0 }}
                  transition={{ delay: 0.15 + i * 0.08 }}
                  whileHover={{ scale: isHidden || revealed ? 1 : 1.02 }}
                  whileTap={{ scale: isHidden || revealed ? 1 : 0.97 }}
                  disabled={isHidden || !!selected || view === 'teacher'}
                  onClick={() => { if (view === 'student') { setSelected(opt); onAnswer?.(opt); } }}
                  style={{
                    background: revealed && isCorrect ? 'linear-gradient(180deg, #3b8f3b, #1f6b1f)'
                      : revealed && isWrongSelected ? 'linear-gradient(180deg, #b91c1c, #7f1d1d)'
                      : isSelected ? 'linear-gradient(180deg, #FFD700, #c9a500)'
                      : 'linear-gradient(180deg, #0a2c5a, #001d3a)',
                    color: isSelected && !revealed ? '#001d3a' : 'white',
                    border: '3px solid #FFD700',
                    borderRadius: 30,
                    padding: '16px 20px',
                    fontSize: 16,
                    fontFamily: "'DM Serif Display', serif",
                    cursor: isHidden || selected || view === 'teacher' ? 'default' : 'pointer',
                    textAlign: 'left',
                  }}>
                  <span style={{ color: isSelected && !revealed ? '#001d3a' : '#FFD700', fontWeight: 'bold', marginRight: 12 }}>
                    {LETTERS[i]}:
                  </span>
                  {opt}
                </motion.button>
              );
            })}
          </div>

          {/* Lifelines (student only) */}
          {view === 'student' && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 28 }}>
              <Lifeline label="50:50" used={fiftyFiftyUsed} onClick={useFiftyFifty} />
              <Lifeline label="AUDIENCE" used={audienceUsed} onClick={() => setAudienceUsed(true)} />
              <Lifeline label="SKIP" used={skipUsed} onClick={() => setSkipUsed(true)} />
            </div>
          )}

          {/* Teacher view — show correct answer */}
          {view === 'teacher' && (
            <div style={{
              marginTop: 20, padding: 12,
              background: 'rgba(255,215,0,0.15)',
              border: '1px solid #FFD700',
              borderRadius: 8,
              textAlign: 'center',
              fontFamily: 'Nunito',
              fontSize: 14,
              color: '#FFD700',
            }}>
              Correct answer: <strong>{question.answer}</strong>
            </div>
          )}
        </div>

        {/* RIGHT — prize ladder */}
        <div style={{
          background: 'linear-gradient(180deg, #001d3a, #000714)',
          border: '2px solid #FFD700',
          borderRadius: 12,
          padding: '12px 10px',
          fontFamily: 'Nunito',
        }}>
          {LADDER.slice().reverse().map((amt, idx) => {
            const tier = 14 - idx;
            const active = tier === currentTier;
            const passed = tier < currentTier;
            const safe = SAFE_TIERS.includes(tier);
            return (
              <div key={tier} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '6px 10px',
                marginBottom: 2,
                borderRadius: 4,
                background: active ? '#FFD700' : passed ? 'rgba(59,143,59,0.4)' : 'transparent',
                color: active ? '#001d3a' : safe ? '#FFD700' : 'white',
                fontWeight: active ? 'bold' : 'normal',
                fontSize: tier === 14 ? 14 : 12,
              }}>
                <span style={{ color: active ? '#001d3a' : '#FFD700', fontWeight: 'bold' }}>
                  {tier + 1}
                </span>
                <span>{amt}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Student result banner */}
      <AnimatePresence>
        {view === 'student' && lastResult && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed', bottom: 32, left: '50%', transform: 'translateX(-50%)',
              padding: '16px 28px',
              background: lastResult.correct ? '#3b8f3b' : '#b91c1c',
              border: '3px solid #FFD700',
              borderRadius: 12,
              color: 'white', fontSize: 18, fontWeight: 'bold',
              fontFamily: 'Nunito',
            }}>
            {lastResult.correct
              ? `Correct! +${lastResult.points} points`
              : `Wrong — correct was ${lastResult.correct_answer}`}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Lifeline({ label, used, onClick }) {
  return (
    <button onClick={onClick} disabled={used}
      style={{
        width: 90, height: 60,
        borderRadius: '50% / 40%',
        border: '3px solid #FFD700',
        background: used ? 'rgba(128,128,128,0.4)' : 'linear-gradient(180deg, #0a2c5a, #001d3a)',
        color: used ? '#666' : '#FFD700',
        fontFamily: 'Nunito', fontWeight: 'bold', fontSize: 12,
        cursor: used ? 'not-allowed' : 'pointer',
        textDecoration: used ? 'line-through' : 'none',
      }}>
      {label}
    </button>
  );
}

function Waiting({ text }) {
  return (
    <div style={{
      background: 'radial-gradient(ellipse at top, #001d3a 0%, #000714 100%)',
      minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#FFD700', fontFamily: "'DM Serif Display', serif", fontSize: 22,
    }}>
      {text}
    </div>
  );
}
