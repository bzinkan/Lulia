'use client';
import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { play } from '@/lib/gameSounds';
import { correctAnswer } from '@/lib/confetti';

/**
 * Memory Match — grid of face-down cards. Student flips two cards:
 * one showing a question, one showing an answer. Match them to score.
 * Self-paced on each device.
 *
 * The deck is built client-side from allQuestions — no new backend data
 * needed. "Answer" events go back to the server using the normal MCQ
 * channel (each successful match = one correct answer event).
 */
export default function MemoryMatch({
  allQuestions = [], question, view = 'student', onAnswer,
  questionIndex = 0, totalQuestions = 0, lastResult = null, playerId = 'anon',
}) {
  // Build deck: 6 Q/A pairs = 12 cards
  const deck = useMemo(() => {
    const pairs = (allQuestions || []).slice(0, 6);
    const cards = [];
    pairs.forEach((q, i) => {
      cards.push({ id: `q${i}`, pairId: i, type: 'Q', text: q.question_text, answer: q.answer });
      cards.push({ id: `a${i}`, pairId: i, type: 'A', text: q.answer, answer: q.answer });
    });
    // Seeded shuffle per playerId
    return seededShuffle(cards, playerId);
  }, [allQuestions, playerId]);

  const [flipped, setFlipped] = useState([]); // currently flipped card ids
  const [matched, setMatched] = useState(new Set());
  const [misses, setMisses] = useState(0);

  function handleClick(card) {
    if (view !== 'student') return;
    if (matched.has(card.pairId)) return;
    if (flipped.length >= 2) return;
    if (flipped.some(f => f.id === card.id)) return;

    const newFlipped = [...flipped, card];
    setFlipped(newFlipped);

    if (newFlipped.length === 2) {
      const [a, b] = newFlipped;
      if (a.pairId === b.pairId) {
        // Match!
        setTimeout(() => {
          play('correct');
          correctAnswer({ x: 0.5, y: 0.5 });
          setMatched(prev => new Set([...prev, a.pairId]));
          setFlipped([]);
          // Report to server as a correct answer
          onAnswer?.(a.answer);
        }, 400);
      } else {
        // Miss
        setTimeout(() => {
          play('incorrect');
          setFlipped([]);
          setMisses(m => m + 1);
        }, 800);
      }
    }
  }

  const allMatched = matched.size === (deck.length / 2);

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #2d1b3d 0%, #1a0d26 100%)',
      color: 'white', fontFamily: 'Nunito', padding: 24,
    }}>
      {/* Header */}
      <div style={{ maxWidth: 1000, margin: '0 auto 20px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 28, color: '#C5A8E8' }}>
          Memory Match
        </h1>
        <div style={{ display: 'flex', gap: 16 }}>
          <Chip label="MATCHED" value={`${matched.size}/${deck.length/2}`} color="#9ED4BC" />
          <Chip label="MISSES" value={misses} color="#FF8A6E" />
        </div>
      </div>

      {allMatched ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{
            maxWidth: 600, margin: '40px auto',
            padding: '40px 24px', textAlign: 'center',
            background: 'linear-gradient(135deg, #9ED4BC, #6BA08A)',
            borderRadius: 20, color: '#1A1416',
          }}>
          <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 36 }}>
            🎉 All Pairs Matched!
          </h2>
          <p style={{ marginTop: 8, fontSize: 16 }}>
            {misses === 0 ? 'Flawless! No misses.' : `${misses} miss${misses === 1 ? '' : 'es'} total.`}
          </p>
        </motion.div>
      ) : (
        <div style={{
          maxWidth: 900, margin: '0 auto',
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12,
        }}>
          {deck.map(card => {
            const isFlipped = flipped.some(f => f.id === card.id) || matched.has(card.pairId);
            const isMatched = matched.has(card.pairId);
            return (
              <MemoryCard key={card.id}
                card={card}
                flipped={isFlipped}
                matched={isMatched}
                onClick={() => handleClick(card)} />
            );
          })}
        </div>
      )}

      {view === 'teacher' && (
        <div style={{
          maxWidth: 600, margin: '32px auto 0',
          padding: 16,
          background: 'rgba(255,255,255,0.05)',
          borderRadius: 12,
          textAlign: 'center',
          fontSize: 13,
          color: 'rgba(255,255,255,0.7)',
        }}>
          Each student is matching pairs on their own device. Watch the leaderboard for completions.
        </div>
      )}
    </div>
  );
}

function MemoryCard({ card, flipped, matched, onClick }) {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: flipped ? 1 : 1.05 }}
      whileTap={{ scale: 0.97 }}
      animate={{ rotateY: flipped ? 180 : 0 }}
      transition={{ duration: 0.35 }}
      style={{
        aspectRatio: '3 / 4',
        padding: 0,
        borderRadius: 12,
        border: 'none',
        cursor: flipped ? 'default' : 'pointer',
        background: 'transparent',
        position: 'relative',
        transformStyle: 'preserve-3d',
        perspective: 600,
      }}>
      {/* Back */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(135deg, #8C5A82, #5C3B52)',
        borderRadius: 12,
        border: '2px solid #C5A8E8',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backfaceVisibility: 'hidden',
        fontSize: 32,
        color: '#FFD87A',
        fontFamily: "'DM Serif Display', serif",
        fontWeight: 'bold',
      }}>
        ?
      </div>
      {/* Front */}
      <div style={{
        position: 'absolute', inset: 0,
        background: matched
          ? 'linear-gradient(135deg, #9ED4BC, #6BA08A)'
          : card.type === 'Q'
            ? 'linear-gradient(135deg, #FFD87A, #DAB04E)'
            : 'linear-gradient(135deg, #A7C9E8, #6B9BC7)',
        color: '#1A1416',
        borderRadius: 12,
        border: '2px solid white',
        padding: 10,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        textAlign: 'center',
        transform: 'rotateY(180deg)',
        backfaceVisibility: 'hidden',
        fontSize: 12,
        fontWeight: 700,
        lineHeight: 1.2,
        overflow: 'hidden',
      }}>
        {card.text}
      </div>
    </motion.button>
  );
}

function Chip({ label, value, color }) {
  return (
    <div style={{
      padding: '6px 14px',
      background: 'rgba(255,255,255,0.08)',
      border: `1px solid ${color}`,
      borderRadius: 8,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 9, letterSpacing: 1.5, color: 'rgba(255,255,255,0.5)' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function seededShuffle(arr, seed) {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); }
  const rng = () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
