'use client';
import { useEffect, useState } from 'react';
import { Joystick, Users, Trophy } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import GenerationTabs from '@/components/GenerationTabs';

const GAME_SHELLS = [
  { id: 'classic_quiz', name: 'Classic Quiz (Kahoot-style)' },
  { id: 'speed_race', name: 'Speed Race' },
  { id: 'team_tug_of_war', name: 'Team Tug of War' },
  { id: 'jeopardy', name: 'Jeopardy' },
  { id: 'millionaire', name: 'Who Wants to Be a Millionaire' },
  { id: 'battle_royale', name: 'Battle Royale' },
  { id: 'card_duel', name: 'Card Duel' },
  { id: 'escape_classroom', name: 'Escape the Classroom' },
];

export default function GamesPage() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  function load() {
    apiFetch('/api/v1/games/sessions').then(d => setSessions(d.sessions || [])).catch(console.error).finally(() => setLoading(false));
  }

  function handleResult(result) {
    if (result?.game?.pin || result?.pin) {
      const pin = result?.game?.pin || result?.pin;
      window.open(`/join`, '_blank');
    }
    load();
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Live Games</h1>
        <p className="text-sm mt-1" style={{ color: '#78716C' }}>Real-time multiplayer games — students join with a Game PIN</p>
      </div>

      {/* Generation tabs */}
      <div className="mb-6">
        <GenerationTabs outputType="game" templates={GAME_SHELLS} templateLabel="Game Type" onResult={handleResult} />
      </div>

      {/* Sessions */}
      {loading ? (
        <div className="animate-pulse space-y-3">{[1,2,3].map(i => <div key={i} className="h-14 rounded-[14px]" style={{ background: '#F5F5F4' }} />)}</div>
      ) : sessions.length === 0 ? (
        <div className="rounded-[14px] p-8 text-center" style={{ background: 'white', border: '1px solid #E7E5E4' }}>
          <Joystick className="w-10 h-10 mx-auto mb-2" style={{ color: '#E7E5E4' }} />
          <p className="text-sm" style={{ color: '#A8A29E' }}>Games you create will appear here</p>
        </div>
      ) : (
        <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
          <table className="w-full text-sm">
            <thead><tr style={{ borderBottom: '1px solid #F5F5F4' }}>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider" style={{ color: '#A8A29E' }}>PIN</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider" style={{ color: '#A8A29E' }}>Game</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider" style={{ color: '#A8A29E' }}>Status</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider" style={{ color: '#A8A29E' }}>Created</th>
            </tr></thead>
            <tbody>
              {sessions.map(s => (
                <tr key={s.session_id || s.pin} className="transition-colors cursor-pointer" style={{ borderBottom: '1px solid #F5F5F4' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#FFF7ED'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td className="px-4 py-3 font-mono font-bold text-lg" style={{ color: '#F97316' }}>{s.pin}</td>
                  <td className="px-4 py-3" style={{ color: '#1C1917' }}>{s.game_shell_id}</td>
                  <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full font-medium ${s.status === 'finished' ? 'bg-green-50 text-green-700' : s.status === 'playing' ? 'bg-orange-50 text-orange-700' : 'bg-gray-100 text-gray-600'}`}>{s.status}</span></td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#A8A29E' }}>{s.created_at ? new Date(s.created_at).toLocaleString() : 'Just now'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
