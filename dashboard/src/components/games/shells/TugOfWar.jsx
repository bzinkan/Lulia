'use client';
import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { play } from '@/lib/gameSounds';

/**
 * Team Tug of War — 2 teams, correct answer pulls the rope toward the team.
 * Team assignment is deterministic from playerId (even hash = A, odd = B).
 *
 * Rope position is tracked client-side based on lastResult accumulated over
 * rounds. Gives a visual illusion of pull even though the server just
 * records points.
 */
const TEAM_A_COLOR = '#D86C52';
const TEAM_B_COLOR = '#6BA08A';

function teamFromPlayerId(playerId) {
  // Even hash → A, odd → B. Deterministic so everyone sees the same team.
  let h = 0;
  for (let i = 0; i < (playerId || '').length; i++) h = (h * 31 + playerId.charCodeAt(i)) | 0;
  return Math.abs(h) % 2 === 0 ? 'A' : 'B';
}

export default function TugOfWar({
  question, players = [], view = 'student', onAnswer,
  questionIndex = 0, totalQuestions = 1, lastResult = null, playerId = 'anon',
}) {
  const [selected, setSelected] = useState(null);
  const [ropePos, setRopePos] = useState(0); // -10 (A wins) to +10 (B wins), 0 center
  const myTeam = useMemo(() => teamFromPlayerId(playerId), [playerId]);

  useEffect(() => { setSelected(null); }, [question?.question_text]);

  useEffect(() => {
    if (!lastResult) return;
    if (lastResult.correct) {
      play('correct');
      // Push rope toward my team (A = negative, B = positive)
      setRopePos(p => Math.max(-10, Math.min(10, p + (myTeam === 'A' ? -1 : 1))));
    } else {
      play('incorrect');
    }
  }, [lastResult]);

  const winnerA = ropePos <= -8;
  const winnerB = ropePos >= 8;

  if (!question) return <Waiting />;

  return (
    <div style={{
      minHeight: '100vh',
      background: `linear-gradient(135deg, ${TEAM_A_COLOR}22 0%, #1a1416 50%, ${TEAM_B_COLOR}22 100%)`,
      color: 'white', fontFamily: 'Nunito', padding: 24,
    }}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        {/* Team header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <TeamBadge team="A" color={TEAM_A_COLOR} isMine={myTeam === 'A'}
            count={players.filter(p => teamFromPlayerId(p.player_id) === 'A').length} />
          <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 28 }}>Tug of War</h1>
          <TeamBadge team="B" color={TEAM_B_COLOR} isMine={myTeam === 'B'}
            count={players.filter(p => teamFromPlayerId(p.player_id) === 'B').length} />
        </div>

        {/* Rope */}
        <div style={{
          position: 'relative',
          height: 80, marginBottom: 32,
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 40,
          overflow: 'hidden',
        }}>
          {/* Center line */}
          <div style={{
            position: 'absolute', top: 0, bottom: 0, left: '50%',
            width: 2, background: 'rgba(255,255,255,0.2)',
          }} />
          {/* Rope knot */}
          <motion.div
            animate={{ left: `${50 + ropePos * 4}%` }}
            transition={{ type: 'spring', stiffness: 140, damping: 18 }}
            style={{
              position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
              width: 60, height: 60, borderRadius: '50%',
              background: ropePos < 0 ? TEAM_A_COLOR : ropePos > 0 ? TEAM_B_COLOR : '#FFD87A',
              boxShadow: `0 0 24px ${ropePos < 0 ? TEAM_A_COLOR : ropePos > 0 ? TEAM_B_COLOR : '#FFD87A'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 30,
            }}>
            🏁
          </motion.div>
          {/* A side tick marks */}
          <div style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
            fontSize: 12, color: TEAM_A_COLOR, fontWeight: 800, letterSpacing: 2 }}>← A</div>
          <div style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
            fontSize: 12, color: TEAM_B_COLOR, fontWeight: 800, letterSpacing: 2 }}>B →</div>
        </div>

        {winnerA || winnerB ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{
              textAlign: 'center', padding: 40,
              background: `linear-gradient(135deg, ${winnerA ? TEAM_A_COLOR : TEAM_B_COLOR}, rgba(0,0,0,0.6))`,
              border: '2px solid white',
              borderRadius: 20,
              fontFamily: "'DM Serif Display', serif",
              fontSize: 40,
            }}>
            🎉 TEAM {winnerA ? 'A' : 'B'} WINS!
          </motion.div>
        ) : (
          <>
            {/* Question */}
            <AnimatePresence mode="wait">
              <motion.h2 key={questionIndex}
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                style={{
                  fontFamily: "'DM Serif Display', serif", fontSize: 26,
                  textAlign: 'center', marginBottom: 24,
                  padding: 24,
                  background: 'rgba(255,255,255,0.05)',
                  border: '2px solid rgba(255,255,255,0.15)',
                  borderRadius: 12,
                }}>
                {question.question_text}
              </motion.h2>
            </AnimatePresence>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {(question.options || []).map((opt, i) => {
                const isSel = selected === opt;
                const isCorrect = lastResult?.correct_answer === opt;
                const isWrongSel = lastResult && isSel && !lastResult.correct;
                const revealed = !!lastResult;
                const teamColor = myTeam === 'A' ? TEAM_A_COLOR : TEAM_B_COLOR;
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
                        : isSel ? teamColor
                        : 'rgba(255,255,255,0.08)',
                      border: `2px solid ${isSel ? teamColor : 'rgba(255,255,255,0.2)'}`,
                      color: 'white', borderRadius: 10,
                      fontSize: 16, fontWeight: 700,
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

function TeamBadge({ team, color, isMine, count }) {
  return (
    <div style={{
      padding: '10px 18px',
      background: color,
      borderRadius: 12,
      boxShadow: isMine ? `0 0 20px ${color}` : 'none',
      border: isMine ? '3px solid white' : 'none',
    }}>
      <div style={{ fontSize: 10, letterSpacing: 2, opacity: 0.8 }}>TEAM {team}</div>
      <div style={{ fontSize: 20, fontWeight: 800 }}>{count} players {isMine && '(YOU)'}</div>
    </div>
  );
}

function Waiting() {
  return <div style={{ minHeight: '100vh', background: '#1a1416',
    color: '#FFD87A', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: 'Nunito', fontSize: 22 }}>Teams forming…</div>;
}
