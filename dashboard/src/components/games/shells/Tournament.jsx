'use client';
import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Trophy } from 'lucide-react';
import { play } from '@/lib/gameSounds';

/**
 * Tournament — single-elim bracket visualization. Each question = one round.
 * Student plays through all questions (normal MCQ flow), but UI shows them
 * as climbing a bracket.
 *
 * Bracket size visible on screen adapts to 4/8/16/32 player count.
 */
export default function Tournament({
  question, players = [], view = 'student', onAnswer,
  questionIndex = 0, totalQuestions = 1, lastResult = null,
}) {
  const [selected, setSelected] = useState(null);
  useEffect(() => { setSelected(null); }, [question?.question_text]);
  useEffect(() => { if (lastResult) { play(lastResult.correct ? 'correct' : 'incorrect'); } }, [lastResult]);

  const bracketSize = useMemo(() => {
    const n = Math.max(4, players.length || 4);
    return [4, 8, 16, 32].find(s => s >= n) || 32;
  }, [players.length]);
  const rounds = Math.log2(bracketSize);
  const currentRound = Math.min(Math.floor(questionIndex / Math.ceil(totalQuestions / rounds)), rounds - 1);

  if (!question) return <Waiting />;

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a1a4a 0%, #0a0a24 100%)',
      color: 'white', fontFamily: 'Nunito', padding: 24,
    }}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 28,
          textAlign: 'center', marginBottom: 8, color: '#FFD87A',
          textShadow: '0 0 16px #DAB04E' }}>
          <Trophy style={{ display: 'inline', width: 28, height: 28, color: '#FFD87A', marginRight: 10 }} />
          Tournament
        </h1>

        {/* Bracket progress */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 24 }}>
          {Array.from({ length: rounds }).map((_, i) => (
            <div key={i} style={{
              padding: '4px 14px',
              borderRadius: 12,
              background: i <= currentRound ? 'linear-gradient(135deg, #FFD87A, #DAB04E)' : 'rgba(255,255,255,0.08)',
              color: i <= currentRound ? '#1a1a4a' : 'rgba(255,255,255,0.4)',
              fontSize: 11, fontWeight: 800, letterSpacing: 2,
              border: i === currentRound ? '2px solid white' : 'none',
            }}>
              {roundLabel(i, rounds)}
            </div>
          ))}
        </div>

        {/* Mini bracket visual */}
        <div style={{
          padding: 16, marginBottom: 24,
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 12,
          display: 'flex', justifyContent: 'space-around', alignItems: 'center',
          minHeight: 120, overflow: 'hidden',
        }}>
          {Array.from({ length: Math.min(rounds, 4) }).map((_, r) => {
            const matchesThisRound = bracketSize / Math.pow(2, r + 1);
            return (
              <div key={r} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {Array.from({ length: Math.min(matchesThisRound, 4) }).map((_, m) => (
                  <div key={m} style={{
                    width: 40, height: 12,
                    background: r <= currentRound ? '#FFD87A' : 'rgba(255,255,255,0.15)',
                    borderRadius: 2,
                  }} />
                ))}
              </div>
            );
          })}
          <Trophy style={{ width: 48, height: 48, color: '#FFD87A',
            filter: 'drop-shadow(0 0 12px #DAB04E)' }} />
        </div>

        {/* Question */}
        <AnimatePresence mode="wait">
          <motion.div key={questionIndex}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            style={{
              padding: 28, marginBottom: 20,
              background: 'linear-gradient(135deg, rgba(255,216,122,0.1), rgba(26,26,74,0.8))',
              border: '2px solid #FFD87A',
              borderRadius: 14,
              textAlign: 'center',
            }}>
            <div style={{ fontSize: 11, letterSpacing: 3, color: '#FFD87A', marginBottom: 8 }}>
              {roundLabel(currentRound, rounds)} — QUESTION {questionIndex + 1}
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
                    : isSel ? 'rgba(255,216,122,0.25)'
                    : 'rgba(255,255,255,0.08)',
                  border: `2px solid ${isSel ? '#FFD87A' : 'rgba(255,255,255,0.15)'}`,
                  color: 'white',
                  borderRadius: 10, fontSize: 15, fontWeight: 700,
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

function roundLabel(round, totalRounds) {
  if (round === totalRounds - 1) return 'FINAL';
  if (round === totalRounds - 2) return 'SEMIS';
  if (round === totalRounds - 3) return 'QUARTERS';
  return `R${round + 1}`;
}

function Waiting() {
  return <div style={{ minHeight: '100vh',
    background: 'linear-gradient(135deg, #1a1a4a 0%, #0a0a24 100%)',
    color: '#FFD87A', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: 'Nunito', fontSize: 22 }}>Seeding brackets…</div>;
}
