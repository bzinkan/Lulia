'use client';
import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { Play, SkipForward, StopCircle, Users, Copy, CheckCircle } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import QuizRace from '@/components/games/shells/QuizRace';
import Jeopardy from '@/components/games/shells/Jeopardy';
import BingoBlitz from '@/components/games/shells/BingoBlitz';

const SHELL_COMPONENTS = {
  quiz_race: QuizRace,
  jeopardy: Jeopardy,
  bingo_blitz: BingoBlitz,
};

export default function TeacherPlayPage() {
  const { pin } = useParams();
  const [state, setState] = useState(null);
  const [copied, setCopied] = useState(false);
  const [ended, setEnded] = useState(null);
  const [calledAnswers, setCalledAnswers] = useState([]);
  const [answeredCells, setAnsweredCells] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!pin) return;
    // Load initial info so we know the shell before WebSocket connects
    apiFetch(`/api/v1/games/${pin}/info`).then(setState).catch(() => {});
    connectWebSocket();
    return () => wsRef.current?.close();
  }, [pin]);

  function connectWebSocket() {
    const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
    const wsPort = 8000;
    wsRef.current = new WebSocket(`${proto}://${host}:${wsPort}/ws/games/${pin}`);
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
      if (msg.type === 'player_joined') {
        next.player_count = msg.player_count;
        next.players = msg.players || next.players;
      } else if (msg.type === 'game_started' || msg.type === 'new_question') {
        next.status = 'playing';
        next.current_question = msg.question;
        next.question_index = msg.current_question ?? next.question_index ?? 0;
        next.total_questions = msg.total_questions ?? next.total_questions ?? 0;
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

  if (!state) {
    return <div className="p-8 text-center" style={{ color: 'var(--text-light)' }}>Loading game…</div>;
  }

  const Shell = SHELL_COMPONENTS[state.game_shell_id];
  const players = state.players || [];

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="rounded-card p-4 mb-4 flex items-center justify-between flex-wrap gap-3"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>Game PIN</span>
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold text-[32px] tracking-wider" style={{ color: 'var(--coral)' }}>{pin}</span>
            <button onClick={copyPin}
              className="p-1.5 rounded-lg"
              style={{ color: 'var(--text-mid)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
              {copied ? <CheckCircle className="w-4 h-4" style={{ color: 'var(--sage)' }} /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-light)' }}>
            Share with students: join at <strong>/join?pin={pin}</strong>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-[14px] font-bold" style={{ color: 'var(--text-dark)' }}>
            <Users className="w-4 h-4" /> {players.length} player{players.length !== 1 ? 's' : ''}
          </div>
          {state.status === 'lobby' && (
            <button onClick={startGame} disabled={players.length === 0}
              className="px-4 py-2 rounded-xl font-bold text-[14px] text-white flex items-center gap-2 disabled:opacity-50"
              style={{ background: 'var(--sage)' }}>
              <Play className="w-4 h-4" /> Start Game
            </button>
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

      {/* Ended view */}
      {ended && (
        <div className="rounded-card p-6 mt-4"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
          <h2 className="font-serif text-[24px] text-center mb-4" style={{ color: 'var(--text-dark)' }}>
            Final Leaderboard
          </h2>
          <div className="space-y-2 max-w-xl mx-auto">
            {ended.leaderboard.map((p, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-xl"
                style={{ background: i === 0 ? 'rgba(233,180,76,0.12)' : 'var(--cream)', border: '1px solid var(--border)' }}>
                <div className="flex items-center gap-3">
                  <span className="font-bold text-[20px]" style={{ color: i === 0 ? 'var(--mustard, #E9B44C)' : 'var(--text-mid)' }}>
                    #{p.rank}
                  </span>
                  <span className="text-[22px]">{p.avatar || '🐻'}</span>
                  <span className="font-serif text-[16px]" style={{ color: 'var(--text-dark)' }}>{p.name}</span>
                </div>
                <span className="font-bold text-[16px]" style={{ color: 'var(--coral)' }}>{p.score}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
