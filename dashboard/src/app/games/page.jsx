'use client';
import { useEffect, useState } from 'react';
import Image from 'next/image';
import { Gamepad2, Play, Clock, Users, Repeat, Loader2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';
import { GAME_SHELLS } from '@/lib/gameShellConfigs';
import GameSetupModal from '@/components/games/GameSetupModal';

export default function GamesPage() {
  const { activeClassId, teacherId } = useClassContext();
  const [sessions, setSessions] = useState([]);
  const [selectedShell, setSelectedShell] = useState(null);
  const [replaying, setReplaying] = useState(null);

  useEffect(() => { loadSessions(); }, [teacherId]);

  async function loadSessions() {
    try {
      const data = await apiFetch(`/api/v1/games/sessions?teacher_id=${teacherId}`);
      setSessions(data.sessions || []);
    } catch {}
  }

  async function handleReplay(sessionId) {
    setReplaying(sessionId);
    try {
      const result = await apiFetch(`/api/v1/games/${sessionId}/replay`, {
        method: 'POST',
        body: JSON.stringify({ teacher_id: teacherId }),
      });
      if (result.pin) {
        window.open(`/play/${result.pin}`, '_blank');
        loadSessions();
      } else {
        alert(result.error || 'Replay failed');
      }
    } catch (e) {
      alert(e.message);
    } finally {
      setReplaying(null);
    }
  }

  function handleLaunched(result) {
    setSelectedShell(null);
    if (result?.pin) window.open(`/play/${result.pin}`, '_blank');
    loadSessions();
  }

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <div className="w-12 h-12 rounded-[14px] flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, var(--coral), var(--coral-light))', boxShadow: '0 4px 14px rgba(216,108,82,0.3)' }}>
          <Gamepad2 className="w-6 h-6 text-white" strokeWidth={2.5} />
        </div>
        <div>
          <h1 className="font-serif text-[28px] leading-tight" style={{ color: 'var(--text-dark)' }}>
            Live Games
          </h1>
          <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
            Free to play. Configure each game to fit your lesson.
          </p>
        </div>
      </div>

      {/* Grid of 12 games */}
      <div className="rounded-card p-5 mb-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
          Choose a game
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {GAME_SHELLS.map(shell => {
            const comingSoon = shell.phase !== 1;
            return (
              <div key={shell.id}
                className="rounded-card p-3 flex flex-col relative overflow-hidden"
                style={{
                  background: 'var(--cream)',
                  border: '1px solid var(--border)',
                  opacity: comingSoon ? 0.65 : 1,
                }}>
                {comingSoon && (
                  <span className="absolute top-0 right-0 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5"
                    style={{
                      background: 'var(--mustard, #E9B44C)',
                      color: 'white',
                      borderBottomLeftRadius: 8,
                    }}>
                    Coming Soon
                  </span>
                )}
                <div className="flex items-center justify-center h-14 mb-2">
                  <GameIcon shell={shell} />
                </div>
                <h3 className="font-serif text-[15px] text-center mb-1" style={{ color: 'var(--text-dark)' }}>
                  {shell.name}
                </h3>
                <p className="text-[11px] text-center mb-2 flex-1" style={{ color: 'var(--text-mid)' }}>
                  {shell.desc}
                </p>
                <div className="flex items-center justify-center gap-3 text-[10px] mb-3" style={{ color: 'var(--text-light)' }}>
                  <span className="flex items-center gap-0.5"><Users className="w-2.5 h-2.5" /> {shell.min_players}+</span>
                  <span className="flex items-center gap-0.5"><Clock className="w-2.5 h-2.5" /> {shell.play_time_min}m</span>
                </div>
                <button
                  onClick={() => setSelectedShell(shell)}
                  disabled={comingSoon}
                  className="w-full py-1.5 rounded-xl text-[12px] font-bold text-white flex items-center justify-center gap-1 disabled:cursor-not-allowed"
                  style={{
                    background: comingSoon ? 'var(--text-light)' : 'var(--coral)',
                    boxShadow: comingSoon ? 'none' : '0 2px 8px rgba(216,108,82,0.25)',
                  }}>
                  <Play className="w-3 h-3" /> {comingSoon ? 'Soon' : 'Launch'}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent sessions with Replay */}
      <div className="rounded-card p-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
          Recent games
        </h2>
        {sessions.length === 0 ? (
          <p className="text-center py-6 text-[13px]" style={{ color: 'var(--text-light)' }}>
            No games yet. Launch one above to get started.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl" style={{ border: '1px solid var(--border)' }}>
            <table className="w-full text-[12px]">
              <thead>
                <tr style={{ background: 'var(--cream)', borderBottom: '1px solid var(--border)' }}>
                  {['Game', 'PIN', 'Status', 'Created', ''].map(h => (
                    <th key={h} className="text-left px-3 py-2 text-[10px] uppercase tracking-wider font-bold"
                      style={{ color: 'var(--text-light)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => {
                  const shell = GAME_SHELLS.find(g => g.id === s.game_shell_id);
                  const statusColor = s.status === 'finished' ? '#16A34A' : s.status === 'playing' ? 'var(--coral)' : '#3B82F6';
                  return (
                    <tr key={s.session_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="px-3 py-2 font-semibold" style={{ color: 'var(--text-dark)' }}>
                        {shell?.name || s.game_shell_id}
                      </td>
                      <td className="px-3 py-2 font-mono" style={{ color: 'var(--coral)' }}>{s.pin}</td>
                      <td className="px-3 py-2">
                        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full"
                          style={{ color: statusColor, background: 'white', border: `1px solid ${statusColor}` }}>
                          {s.status}
                        </span>
                      </td>
                      <td className="px-3 py-2" style={{ color: 'var(--text-light)' }}>
                        {s.created_at ? new Date(s.created_at).toLocaleString() : ''}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button onClick={() => handleReplay(s.session_id)}
                          disabled={replaying === s.session_id}
                          className="text-[11px] font-semibold px-2.5 py-1 rounded-lg flex items-center gap-1 ml-auto"
                          style={{ color: 'var(--sage)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                          {replaying === s.session_id
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <Repeat className="w-3 h-3" />}
                          Replay (free)
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedShell && (
        <GameSetupModal
          shell={selectedShell}
          teacherId={teacherId}
          classId={activeClassId}
          onLaunched={handleLaunched}
          onClose={() => setSelectedShell(null)}
        />
      )}
    </div>
  );
}

function GameIcon({ shell }) {
  const [src, setSrc] = useState(`/icons/${shell.icon}`);
  return (
    <Image src={src} alt=""
      width={48} height={48}
      onError={() => setSrc(`/icons/${shell.icon_fallback || 'gamepad.png'}`)} />
  );
}
