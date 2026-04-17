'use client';
import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Gamepad2, Loader2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { getGameWebSocketUrl } from '@/lib/gameWebSocket';
import LulingSelector from '@/components/LulingSelector';
import dynamic from 'next/dynamic';
import CabinetStage from '@/components/games/CabinetStage';
import { getShell } from '@/lib/gameShellConfigs';
// Shells use Web Audio + canvas-confetti — client-only, no SSR.
// Arcade v2 lineup: Quiz Race, Jeopardy, Bingo, Millionaire, Memory Match + 4 Phase-2 games.
const QuizRace     = dynamic(() => import('@/components/games/shells/QuizRace'),     { ssr: false });
const Jeopardy     = dynamic(() => import('@/components/games/shells/Jeopardy'),     { ssr: false });
const BingoBlitz   = dynamic(() => import('@/components/games/shells/BingoBlitz'),   { ssr: false });
const Millionaire  = dynamic(() => import('@/components/games/shells/Millionaire'),  { ssr: false });
const MemoryMatch  = dynamic(() => import('@/components/games/shells/MemoryMatch'),  { ssr: false });
const MathBee      = dynamic(() => import('@/components/games/shells/MathBee'),      { ssr: false });
const HistoryQuest = dynamic(() => import('@/components/games/shells/HistoryQuest'), { ssr: false });
const GeoExplorer  = dynamic(() => import('@/components/games/shells/GeoExplorer'),  { ssr: false });
const WordScramble = dynamic(() => import('@/components/games/shells/WordScramble'), { ssr: false });

const SHELL_COMPONENTS = {
  quiz_race: QuizRace,
  jeopardy: Jeopardy,
  bingo_blitz: BingoBlitz,
  millionaire: Millionaire,
  memory_match: MemoryMatch,
  math_bee: MathBee,
  history_quest: HistoryQuest,
  geo_explorer: GeoExplorer,
  word_scramble: WordScramble,
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
  // Live roster used by shells that visualize multi-player state (e.g. Quiz
  // Race racetrack). Server broadcasts player_joined + player_answered to
  // every connection; we just accumulate them here and pass to the shell.
  const [livePlayers, setLivePlayers] = useState([]);
  const [bingoWinner, setBingoWinner] = useState(null); // { player_id, player_name, player_avatar }
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
    const ws = new WebSocket(getGameWebSocketUrl(pin));
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
        // Reflect my own score delta locally so the racetrack updates even
        // before the broadcast `player_answered` arrives.
        if (typeof msg.new_score === 'number') {
          setLivePlayers(prev => prev.map(p =>
            p.player_id === playerId ? { ...p, score: msg.new_score } : p
          ));
        }
      } else if (msg.type === 'player_joined') {
        // Server broadcasts the full players array with each join
        if (Array.isArray(msg.players)) {
          setLivePlayers(msg.players.map(p => ({ ...p, score: p.score ?? 0 })));
        } else if (msg.player) {
          setLivePlayers(prev => {
            if (prev.some(x => x.player_id === msg.player.player_id)) return prev;
            return [...prev, { ...msg.player, score: 0 }];
          });
        }
      } else if (msg.type === 'player_answered') {
        // Score tick for some player (could be me, could be classmate)
        setLivePlayers(prev => {
          const idx = prev.findIndex(p => p.player_id === msg.player_id);
          if (idx < 0) {
            // Unknown player — roster was stale; stub them in
            return [...prev, { player_id: msg.player_id, name: 'Player', score: msg.new_score ?? 0 }];
          }
          return prev.map(p => p.player_id === msg.player_id
            ? { ...p, score: msg.new_score ?? p.score }
            : p);
        });
      } else if (msg.type === 'bingo_claimed') {
        setBingoWinner({
          player_id: msg.player_id,
          player_name: msg.player_name,
          player_avatar: msg.player_avatar,
        });
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

  function submitAnswer(answer, wager) {
    wsRef.current?.send(JSON.stringify({
      type: 'answer',
      player_id: playerId,
      answer,
      time_taken: 0,
      // Only present for Jeopardy-style games; backend treats undefined as decay-scoring.
      ...(typeof wager === 'number' ? { wager } : {}),
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

      {/* Playing step — full viewport, render the shell inside arcade CabinetStage */}
      {step === 'playing' && Shell && (() => {
        const shellMeta = getShell(gameInfo?.game_shell_id) || {};
        return (
          <div style={{ width: '100%' }}>
            <CabinetStage
              gameName={shellMeta.marquee_name || gameInfo?.title || 'LULIA ARCADE'}
              tagline={shellMeta.arcade_tagline || ''}
              accent={shellMeta.accentColor || '#FFBE0B'}
            >
              <Shell
                view="student"
                question={currentQuestion}
                allQuestions={allQuestions}
                players={livePlayers}
                config={gameInfo?.settings || {}}
                questionIndex={questionIndex}
                totalQuestions={totalQuestions}
                playerId={playerId || 'anon'}
                calledAnswers={calledAnswers}
                lastResult={lastResult}
                bingoWinner={bingoWinner}
                onAnswer={submitAnswer}
                onBingo={reportBingo}
              />
            </CabinetStage>
          </div>
        );
      })()}

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
