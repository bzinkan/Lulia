'use client';
import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Gamepad2, Loader2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import LulingSelector from '@/components/LulingSelector';
import QuizRace from '@/components/games/shells/QuizRace';
import Jeopardy from '@/components/games/shells/Jeopardy';
import BingoBlitz from '@/components/games/shells/BingoBlitz';

const SHELL_COMPONENTS = {
  quiz_race: QuizRace,
  jeopardy: Jeopardy,
  bingo_blitz: BingoBlitz,
};

function JoinInner() {
  const params = useSearchParams();
  const initialPin = params.get('pin') || '';

  const [pin, setPin] = useState(initialPin);
  const [name, setName] = useState('');
  const [avatar, setAvatar] = useState(null);
  const [avatarDisplay, setAvatarDisplay] = useState('🐻');
  const [step, setStep] = useState(initialPin ? 'name' : 'pin');
  const [gameInfo, setGameInfo] = useState(null);
  const [error, setError] = useState('');
  const [playerId, setPlayerId] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [lastResult, setLastResult] = useState(null);
  const [calledAnswers, setCalledAnswers] = useState([]);
  const [allQuestions, setAllQuestions] = useState([]);
  const [finalLeaderboard, setFinalLeaderboard] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    // Auto-check pin if provided via URL
    if (initialPin && initialPin.length >= 4) {
      apiFetch(`/api/v1/games/${initialPin}/info`)
        .then(data => {
          if (data.status === 'lobby') {
            setGameInfo(data);
            setStep('name');
          } else {
            setError(data.status === 'playing' ? 'Game has already started' : 'Game not found');
          }
        })
        .catch(() => setError('Game not found'));
    }
  }, [initialPin]);

  async function checkPin() {
    setError('');
    try {
      const data = await apiFetch(`/api/v1/games/${pin}/info`);
      if (data.status === 'lobby') {
        setGameInfo(data);
        setStep('name');
      } else {
        setError('Game has already started');
      }
    } catch {
      setError('Game not found');
    }
  }

  function joinGame() {
    if (!name.trim()) return;
    setError('');
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.hostname;
    const ws = new WebSocket(`${proto}://${host}:8000/ws/games/${pin}`);
    wsRef.current = ws;

    ws.onopen = () => {
      // Don't advance the UI yet — wait for `joined` confirmation from server
      ws.send(JSON.stringify({
        type: 'join',
        name: name.trim(),
        avatar: avatarDisplay,
      }));
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'joined') {
        setPlayerId(msg.player_id);
        setStep('lobby');
      } else if (msg.type === 'error') {
        setError(msg.message || 'Could not join game');
        ws.close();
      } else if (msg.type === 'game_started' || msg.type === 'new_question') {
        setCurrentQuestion(msg.question);
        setQuestionIndex(msg.current_question ?? 0);
        setTotalQuestions(msg.total_questions ?? 0);
        setLastResult(null);
        setStep('playing');
        if (msg.question?.answer) {
          setCalledAnswers(prev => [...prev, msg.question.answer]);
        }
        if (msg.all_questions) setAllQuestions(msg.all_questions);
      } else if (msg.type === 'current_question') {
        // Late-join sync: game already in playing state
        setCurrentQuestion(msg.question);
        setQuestionIndex(msg.current_question ?? 0);
        setTotalQuestions(msg.total_questions ?? 0);
        if (msg.all_questions) setAllQuestions(msg.all_questions);
        setStep('playing');
      } else if (msg.type === 'answer_result') {
        setLastResult({ correct: msg.correct, points: msg.points, correct_answer: msg.correct_answer });
      } else if (msg.type === 'game_finished') {
        setFinalLeaderboard(msg.leaderboard || []);
        setStep('finished');
      }
    };

    ws.onerror = () => setError('Connection lost — check that the API is running');
    ws.onclose = (ev) => {
      if (ev.code === 4004) setError('Game not found');
    };
  }

  function submitAnswer(answer) {
    wsRef.current?.send(JSON.stringify({
      type: 'answer',
      player_id: playerId,
      answer,
      time_taken: 0,
    }));
  }

  function reportBingo() {
    wsRef.current?.send(JSON.stringify({ type: 'bingo', player_id: playerId }));
  }

  const Shell = SHELL_COMPONENTS[gameInfo?.game_shell_id];

  return (
    <div style={{
      background: 'var(--warm-bg, #F5DEC3)',
      minHeight: '100vh',
      padding: 16,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {/* Pin + Name + Lobby steps use the centered card layout */}
      {(step === 'pin' || step === 'name' || step === 'lobby') && (
        <div style={{
          maxWidth: 420, width: '100%',
          background: 'var(--warm-card, #FEF9F2)',
          borderRadius: 20, padding: 32, textAlign: 'center',
          boxShadow: '0 8px 32px rgba(60,40,20,0.15)',
        }}>
          <div style={{
            width: 56, height: 56,
            borderRadius: 16,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            background: 'linear-gradient(135deg, var(--coral, #D86C52), var(--coral-light, #E8927A))',
            marginBottom: 12,
          }}>
            <Gamepad2 style={{ width: 28, height: 28, color: 'white' }} />
          </div>

          {step === 'pin' && (
            <>
              <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 26, color: 'var(--text-dark)', marginBottom: 6 }}>
                Join a Game
              </h1>
              <p style={{ fontSize: 13, color: 'var(--text-mid)', marginBottom: 20 }}>
                Enter the Game PIN from your teacher's screen
              </p>
              <input value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000" maxLength={6}
                style={{
                  width: '100%', textAlign: 'center',
                  fontSize: 36, fontWeight: 700, fontFamily: 'monospace', letterSpacing: 8,
                  border: '2px solid var(--border)', borderRadius: 14, padding: '14px 16px',
                  outline: 'none', background: 'white', color: 'var(--coral, #D86C52)',
                }} />
              {error && <p style={{ color: '#EF4444', fontSize: 13, marginTop: 8 }}>{error}</p>}
              <button onClick={checkPin} disabled={pin.length < 4}
                style={{
                  width: '100%', marginTop: 16,
                  background: 'var(--coral, #D86C52)', color: 'white', border: 'none',
                  padding: '14px', borderRadius: 14,
                  fontSize: 16, fontWeight: 600, cursor: 'pointer',
                  opacity: pin.length < 4 ? 0.5 : 1,
                  boxShadow: '0 4px 14px rgba(216,108,82,0.3)',
                }}>
                Next
              </button>
            </>
          )}

          {step === 'name' && (
            <>
              <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 22, color: 'var(--text-dark)', marginBottom: 4 }}>
                {gameInfo?.title || 'Ready to play'}
              </h1>
              <p style={{ fontSize: 13, color: 'var(--text-mid)', marginBottom: 16 }}>
                Pick your Luling and enter your name
              </p>
              <LulingSelector
                onSelect={(l) => { setAvatar(l); setAvatarDisplay(l.emoji || l.name?.[0] || '🌟'); }}
                selected={avatar?.luling_id}
                showCategories={false}
              />
              <input value={name} onChange={e => setName(e.target.value)}
                placeholder="Your name"
                style={{
                  width: '100%', marginTop: 12,
                  border: '2px solid var(--border)', borderRadius: 14,
                  padding: '12px 16px', fontSize: 16,
                  outline: 'none', textAlign: 'center',
                }} />
              {error && <p style={{ color: '#EF4444', fontSize: 13, marginTop: 8 }}>{error}</p>}
              <button onClick={joinGame} disabled={!name.trim()}
                style={{
                  width: '100%', marginTop: 12,
                  background: 'var(--coral, #D86C52)', color: 'white', border: 'none',
                  padding: '14px', borderRadius: 14,
                  fontSize: 16, fontWeight: 600, cursor: 'pointer',
                  opacity: !name.trim() ? 0.5 : 1,
                }}>
                Let's go, {avatar?.name || name || 'player'}!
              </button>
            </>
          )}

          {step === 'lobby' && (
            <>
              <div style={{ fontSize: 48, marginBottom: 8 }}>
                {avatar?.thumbnail_url
                  ? <img src={avatar.thumbnail_url} alt={avatar.name} style={{ width: 72, height: 72, borderRadius: 16, margin: '0 auto' }} />
                  : avatarDisplay}
              </div>
              <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 22, color: 'var(--text-dark)' }}>
                You're in, {name}!
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-mid)', marginTop: 8 }}>
                Waiting for teacher to start the game…
              </p>
              <div style={{ marginTop: 20 }}>
                <Loader2 style={{ width: 32, height: 32, color: 'var(--coral, #D86C52)', margin: '0 auto', animation: 'spin 1s linear infinite' }} />
              </div>
            </>
          )}
        </div>
      )}

      {/* Playing step — full viewport, render the shell */}
      {step === 'playing' && Shell && (
        <div style={{ width: '100%', maxWidth: 900, padding: 20 }}>
          <Shell
            view="student"
            question={currentQuestion}
            allQuestions={allQuestions}
            players={[]}
            config={gameInfo?.settings || {}}
            questionIndex={questionIndex}
            totalQuestions={totalQuestions}
            playerId={playerId || 'anon'}
            calledAnswers={calledAnswers}
            lastResult={lastResult}
            onAnswer={submitAnswer}
            onBingo={reportBingo}
          />
        </div>
      )}

      {/* Finished step */}
      {step === 'finished' && (
        <div style={{
          maxWidth: 500, width: '100%',
          background: 'var(--warm-card, #FEF9F2)',
          borderRadius: 20, padding: 32, textAlign: 'center',
          boxShadow: '0 8px 32px rgba(60,40,20,0.15)',
        }}>
          <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 28, color: 'var(--text-dark)', marginBottom: 16 }}>
            Game Over!
          </h1>
          {finalLeaderboard && finalLeaderboard.length > 0 && (
            <div style={{ textAlign: 'left' }}>
              {finalLeaderboard.slice(0, 10).map((p, i) => (
                <div key={i} style={{
                  padding: 10, marginBottom: 6,
                  borderRadius: 12,
                  background: i === 0 ? 'rgba(233,180,76,0.12)' : 'var(--cream, #F5EDE0)',
                  border: '1px solid var(--border, #E7E5E4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-dark)' }}>
                    #{p.rank} {p.avatar || '🐻'} {p.name}
                  </span>
                  <span style={{ color: 'var(--coral, #D86C52)', fontWeight: 700 }}>{p.score}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default function JoinPage() {
  return (
    <Suspense fallback={<div className="p-8">Loading…</div>}>
      <JoinInner />
    </Suspense>
  );
}
