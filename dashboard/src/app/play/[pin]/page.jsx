'use client';
import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, SkipForward, StopCircle, Users, Copy, CheckCircle, ExternalLink, Eye, Trophy } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { getGameWebSocketUrl } from '@/lib/gameWebSocket';
import { play as playSound } from '@/lib/gameSounds';
import { winnerCelebration } from '@/lib/confetti';
import dynamic from 'next/dynamic';
const QuizRace    = dynamic(() => import('@/components/games/shells/QuizRace'),    { ssr: false });
const Jeopardy    = dynamic(() => import('@/components/games/shells/Jeopardy'),    { ssr: false });
const BingoBlitz  = dynamic(() => import('@/components/games/shells/BingoBlitz'),  { ssr: false });

const SHELL_COMPONENTS = {
  quiz_race: QuizRace,
  jeopardy: Jeopardy,
  bingo_blitz: BingoBlitz,
};

export default function TeacherPlayPage() {
  const { pin } = useParams();
  const [state, setState] = useState(null);
  const [copied, setCopied] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [ended, setEnded] = useState(null);
  const [calledAnswers, setCalledAnswers] = useState([]);
  const [answeredCells, setAnsweredCells] = useState([]);
  const wsRef = useRef(null);

  const joinUrl = typeof window !== 'undefined' ? `${window.location.origin}/join?pin=${pin}` : '';

  useEffect(() => {
    if (!pin) return;
    // Load initial info so we know the shell before WebSocket connects
    apiFetch(`/api/v1/games/${pin}/info`).then(setState).catch(() => {});
    connectWebSocket();
    return () => wsRef.current?.close();
  }, [pin]);

  function connectWebSocket() {
    wsRef.current = new WebSocket(getGameWebSocketUrl(pin));
    wsRef.current.onopen = () => {
      wsRef.current.send(JSON.stringify({ type: 'teacher_connect' }));
    };
    wsRef.current.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      handleMessage(msg);
    };
  }

  function handleMessage(msg) {
    setState(prev => {
      const next = { ...(prev || {}) };
      if (msg.type === 'game_state') {
        // Teacher snapshot on connect — pulls everything needed to render the board
        const s = msg.state || {};
        next.status = s.status;
        next.title = s.title;
        next.game_shell_id = s.game_shell_id;
        next.players = s.players || [];
        next.question_index = s.current_question ?? -1;
        next.total_questions = s.total_questions ?? 0;
        next.questions = s.all_questions || [];
        next.settings = s.settings || {};
        // If a game is already mid-flight, set current_question
        if (s.current_question >= 0 && next.questions[s.current_question]) {
          next.current_question = next.questions[s.current_question];
        }
      } else if (msg.type === 'player_joined') {
        next.player_count = msg.player_count;
        next.players = msg.players || next.players;
      } else if (msg.type === 'game_started' || msg.type === 'new_question') {
        next.status = 'playing';
        next.current_question = msg.question;
        next.question_index = msg.current_question ?? next.question_index ?? 0;
        next.total_questions = msg.total_questions ?? next.total_questions ?? 0;
        // game_started broadcasts the full question pool so shells can build their boards
        if (msg.all_questions) next.questions = msg.all_questions;
        if (next.game_shell_id === 'bingo_blitz' && msg.question?.answer) {
          setCalledAnswers(prev => [...prev, msg.question.answer]);
        }
      } else if (msg.type === 'player_answered') {
        next.players = (next.players || []).map(p =>
          p.player_id === msg.player_id ? { ...p, score: msg.new_score ?? p.score } : p
        );
      } else if (msg.type === 'leaderboard') {
        next.leaderboard = msg.leaderboard;
      } else if (msg.type === 'game_finished') {
        next.status = 'finished';
        setEnded({ leaderboard: msg.leaderboard || [] });
        // Fire the celebration moment
        setTimeout(() => { playSound('drumroll'); }, 150);
        setTimeout(() => { playSound('fanfare'); winnerCelebration(); }, 1200);
      }
      return next;
    });
  }

  function send(payload) {
    wsRef.current?.send(JSON.stringify(payload));
  }

  async function startGame() {
    await apiFetch(`/api/v1/games/${pin}/start`, { method: 'POST' });
    send({ type: 'start_game' });
  }

  function nextQuestion() {
    send({ type: 'next_question' });
    // For Jeopardy, track which cells have been picked
    if (state?.game_shell_id === 'jeopardy' && typeof state.question_index === 'number') {
      setAnsweredCells(prev => [...prev, state.question_index]);
    }
  }

  function pickJeopardyCell(index) {
    send({ type: 'pick_question', index });
  }

  async function endGame() {
    await apiFetch(`/api/v1/games/${pin}/end`, { method: 'POST' });
    send({ type: 'end_game' });
  }

  function copyPin() {
    navigator.clipboard.writeText(pin);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function copyJoinUrl() {
    navigator.clipboard.writeText(joinUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 1500);
  }

  if (!state) {
    return <div className="p-8 text-center" style={{ color: 'var(--text-light)' }}>Loading game…</div>;
  }

  const Shell = SHELL_COMPONENTS[state.game_shell_id];
  const players = state.players || [];

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="rounded-card p-5 mb-4"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <div className="flex items-start justify-between flex-wrap gap-4">
          {/* Join info — left */}
          <div className="flex items-center gap-4 flex-wrap">
            {/* QR code */}
            {joinUrl && (
              <div className="p-2 rounded-xl" style={{ background: 'white', border: '1px solid var(--border)' }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=120x120&margin=0&data=${encodeURIComponent(joinUrl)}`}
                  alt="Join QR" width={120} height={120}
                />
              </div>
            )}
            {/* PIN + URL block */}
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
                Game PIN
              </span>
              <div className="flex items-center gap-2 mb-2">
                <span className="font-mono font-bold text-[40px] leading-none tracking-wider" style={{ color: 'var(--coral)' }}>{pin}</span>
                <button onClick={copyPin}
                  className="p-2 rounded-lg"
                  style={{ color: 'var(--text-mid)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}
                  title="Copy PIN">
                  {copied ? <CheckCircle className="w-4 h-4" style={{ color: 'var(--sage)' }} /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
              <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
                Or share this link
              </span>
              <div className="flex items-center gap-2 mt-1">
                <a href={joinUrl} target="_blank" rel="noreferrer"
                  className="text-[13px] font-semibold flex items-center gap-1 underline"
                  style={{ color: 'var(--coral)' }}>
                  {joinUrl.replace(/^https?:\/\//, '')}
                  <ExternalLink className="w-3 h-3" />
                </a>
                <button onClick={copyJoinUrl}
                  className="p-1.5 rounded-lg"
                  style={{ color: 'var(--text-mid)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}
                  title="Copy link">
                  {copiedUrl ? <CheckCircle className="w-3.5 h-3.5" style={{ color: 'var(--sage)' }} /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>

          {/* Controls — right */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1 text-[14px] font-bold px-3 py-2 rounded-xl"
              style={{ color: 'var(--text-dark)', background: 'var(--cream)', border: '1px solid var(--border)' }}>
              <Users className="w-4 h-4" /> {players.length} player{players.length !== 1 ? 's' : ''}
            </div>
            {state.status === 'lobby' && (
              <>
                {players.length === 0 && (
                  <button onClick={startGame}
                    className="px-3 py-2 rounded-xl font-semibold text-[12px] flex items-center gap-1.5"
                    style={{ color: 'var(--text-mid)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}
                    title="Start without players — just for previewing the game">
                    <Eye className="w-3.5 h-3.5" /> Preview
                  </button>
                )}
                <button onClick={startGame}
                  className="px-4 py-2 rounded-xl font-bold text-[14px] text-white flex items-center gap-2"
                  style={{ background: 'var(--sage)', opacity: players.length === 0 ? 0.7 : 1 }}>
                  <Play className="w-4 h-4" /> Start Game
                </button>
              </>
            )}
            {state.status === 'playing' && (
              <>
                <button onClick={nextQuestion}
                  className="px-4 py-2 rounded-xl font-bold text-[14px] text-white flex items-center gap-2"
                  style={{ background: 'var(--coral)' }}>
                  <SkipForward className="w-4 h-4" /> Next
                </button>
                <button onClick={endGame}
                  className="px-3 py-2 rounded-xl font-bold text-[13px] flex items-center gap-2"
                  style={{ color: '#B91C1C', background: 'var(--cream)', border: '1px solid #EF4444', cursor: 'pointer' }}>
                  <StopCircle className="w-4 h-4" /> End
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Lobby view */}
      {state.status === 'lobby' && (
        <div className="rounded-card p-8 text-center"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
          <h2 className="font-serif text-[22px] mb-2" style={{ color: 'var(--text-dark)' }}>
            Waiting for students to join…
          </h2>
          <p className="text-[13px] mb-4" style={{ color: 'var(--text-mid)' }}>
            Students visit <strong>/join</strong> and enter the PIN above.
          </p>
          <div className="grid grid-cols-4 md:grid-cols-6 gap-2">
            {players.map(p => (
              <div key={p.player_id} className="rounded-xl p-2"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                <div className="text-[24px] text-center">{p.avatar || '🐻'}</div>
                <div className="text-[11px] font-bold text-center truncate" style={{ color: 'var(--text-dark)' }}>
                  {p.name}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Playing view */}
      {state.status === 'playing' && Shell && (
        <Shell
          view="teacher"
          question={state.current_question}
          allQuestions={state.questions || []}
          players={players}
          config={state.settings || {}}
          questionIndex={state.question_index || 0}
          totalQuestions={state.total_questions || 0}
          answeredCells={answeredCells}
          calledAnswers={calledAnswers}
          onPickCell={pickJeopardyCell}
          onCallNext={nextQuestion}
        />
      )}

      {/* Ended view — staggered leaderboard reveal */}
      <AnimatePresence>
        {ended && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="rounded-card p-8 mt-4"
            style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
            <motion.h2
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 22 }}
              className="font-serif text-[32px] text-center mb-2"
              style={{ color: 'var(--text-dark)' }}>
              Game Over!
            </motion.h2>
            <motion.p
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
              className="text-center text-[14px] mb-6" style={{ color: 'var(--text-mid)' }}>
              Final Leaderboard
            </motion.p>

            <div className="max-w-xl mx-auto space-y-2">
              {[...ended.leaderboard]
                .sort((a, b) => a.rank - b.rank)
                .map((p, i) => (
                  <motion.div key={`${p.name}-${i}`}
                    initial={{ opacity: 0, x: i === 0 ? 0 : -40, scale: i === 0 ? 0.85 : 1 }}
                    animate={{ opacity: 1, x: 0, scale: 1 }}
                    transition={{
                      delay: 1.4 + (ended.leaderboard.length - i) * 0.18,
                      type: 'spring', stiffness: 300, damping: 22,
                    }}
                    className="flex items-center justify-between p-4 rounded-xl"
                    style={{
                      background: i === 0
                        ? 'linear-gradient(135deg, rgba(233,180,76,0.18), rgba(233,180,76,0.08))'
                        : 'var(--cream)',
                      border: `2px solid ${i === 0 ? 'var(--mustard, #E9B44C)' : 'var(--border)'}`,
                      boxShadow: i === 0 ? '0 6px 20px rgba(233,180,76,0.25)' : 'none',
                    }}>
                    <div className="flex items-center gap-4">
                      <span className="font-bold text-[24px] w-10 text-center" style={{
                        color: i === 0 ? '#B48838' : i === 1 ? '#78716C' : i === 2 ? '#92400E' : 'var(--text-mid)',
                      }}>
                        {i === 0 ? '🏆' : `#${p.rank}`}
                      </span>
                      <span className="text-[28px]">{p.avatar || '🐻'}</span>
                      <span className="font-serif" style={{
                        color: 'var(--text-dark)',
                        fontSize: i === 0 ? 22 : 16,
                        fontWeight: i === 0 ? 700 : 500,
                      }}>
                        {p.name}
                      </span>
                    </div>
                    <motion.span
                      initial={{ scale: 0 }} animate={{ scale: 1 }}
                      transition={{ delay: 1.6 + (ended.leaderboard.length - i) * 0.18, type: 'spring', stiffness: 400 }}
                      className="font-bold" style={{
                        color: 'var(--coral)',
                        fontSize: i === 0 ? 22 : 16,
                      }}>
                      {p.score}
                    </motion.span>
                  </motion.div>
                ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
