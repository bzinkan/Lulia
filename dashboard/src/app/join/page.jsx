'use client';
import { useState } from 'react';
import { Gamepad2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import LulingSelector from '@/components/LulingSelector';

export default function JoinPage() {
  const [pin, setPin] = useState('');
  const [name, setName] = useState('');
  const [avatar, setAvatar] = useState(null); // Luling object or null
  const [avatarDisplay, setAvatarDisplay] = useState('🐻');
  const [step, setStep] = useState('pin'); // pin ��� name → lobby → playing
  const [gameInfo, setGameInfo] = useState(null);
  const [error, setError] = useState('');

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
    } catch (e) { setError('Game not found'); }
  }

  function joinGame() {
    if (!name.trim()) return;
    // Connect via WebSocket
    const ws = new WebSocket(`ws://localhost:8000/ws/games/${pin}`);
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'join', name, avatar }));
      setStep('lobby');
    };
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'game_started') setStep('playing');
    };
    ws.onerror = () => setError('Connection failed');
  }

  return (
    <div style={{ background: '#F5DEC3', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ maxWidth: 400, width: '100%', background: '#FEF9F2', borderRadius: 20, padding: 32, textAlign: 'center' }}>
        <Gamepad2 style={{ width: 40, height: 40, color: '#F97316', margin: '0 auto 12px' }} />

        {step === 'pin' && (
          <>
            <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 24, color: '#1C1917', marginBottom: 8 }}>Join a Game</h1>
            <p style={{ fontSize: 13, color: '#78716C', marginBottom: 20 }}>Enter the Game PIN from your teacher's screen</p>
            <input value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="Game PIN" maxLength={6} style={{ width: '100%', textAlign: 'center', fontSize: 32, fontWeight: 700, fontFamily: 'monospace', letterSpacing: 8, border: '2px solid #E7E5E4', borderRadius: 14, padding: '12px 16px', outline: 'none', background: 'white' }} />
            {error && <p style={{ color: '#EF4444', fontSize: 13, marginTop: 8 }}>{error}</p>}
            <button onClick={checkPin} disabled={pin.length < 4} style={{ width: '100%', marginTop: 16, background: '#F97316', color: 'white', border: 'none', padding: '14px', borderRadius: 14, fontSize: 16, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans'" }}>Join</button>
          </>
        )}

        {step === 'name' && (
          <>
            <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 22, color: '#1C1917', marginBottom: 4 }}>{gameInfo?.title}</h1>
            <p style={{ fontSize: 13, color: '#78716C', marginBottom: 16 }}>Pick your Luling and enter your name</p>
            <LulingSelector
              onSelect={(l) => { setAvatar(l); setAvatarDisplay(l.emoji || l.name?.[0] || '🌟'); }}
              selected={avatar?.luling_id}
              showCategories={false}
            />
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" style={{ width: '100%', marginTop: 12, border: '2px solid #E7E5E4', borderRadius: 14, padding: '12px 16px', fontSize: 16, outline: 'none', textAlign: 'center', fontFamily: "'DM Sans'" }} />
            <button onClick={joinGame} disabled={!name.trim()} style={{ width: '100%', marginTop: 12, background: '#F97316', color: 'white', border: 'none', padding: '14px', borderRadius: 14, fontSize: 16, fontWeight: 600, cursor: 'pointer', fontFamily: "'DM Sans'" }}>Let's Go! {avatar?.name || avatarDisplay}</button>
          </>
        )}

        {step === 'lobby' && (
          <>
            <div style={{ fontSize: 48, marginBottom: 8 }}>{avatar?.thumbnail_url ? <img src={avatar.thumbnail_url} alt={avatar.name} style={{ width: 64, height: 64, borderRadius: 16, margin: '0 auto' }} /> : avatarDisplay}</div>
            <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 20, color: '#1C1917' }}>You're in, {name}!</h2>
            <p style={{ fontSize: 13, color: '#78716C', marginTop: 8 }}>Waiting for teacher to start the game...</p>
            <div style={{ marginTop: 16 }}>
              <div style={{ width: 32, height: 32, border: '3px solid #F97316', borderTopColor: 'transparent', borderRadius: '50%', margin: '0 auto', animation: 'spin 1s linear infinite' }} />
            </div>
          </>
        )}

        {step === 'playing' && (
          <p style={{ fontSize: 16, color: '#F97316', fontWeight: 600 }}>Game is live! Check your answers on the main screen.</p>
        )}

        <p style={{ fontSize: 11, color: '#A8A29E', marginTop: 20 }}>Powered by Lulia AI</p>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
