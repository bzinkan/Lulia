'use client';
import { useEffect, useState } from 'react';
import { Gamepad2, Plus, Users, Trophy, Play } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function GamesPage() {
  const [sessions, setSessions] = useState([]);
  const [shells, setShells] = useState([]);
  const [loading, setLoading] = useState(true);
  const [assignmentId, setAssignmentId] = useState('');
  const [shellId, setShellId] = useState('classic_quiz');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/games/sessions').then(d => setSessions(d.sessions || [])),
      apiFetch('/api/v1/games/shells').then(d => setShells(d.shells || [])),
    ]).catch(console.error).finally(() => setLoading(false));
  }, []);

  async function handleCreate() {
    if (!assignmentId) return;
    setCreating(true);
    try {
      const result = await apiFetch('/api/v1/games/create', {
        method: 'POST',
        body: JSON.stringify({ assignment_id: assignmentId, game_shell_id: shellId }),
      });
      if (result.pin) {
        window.open(`/games/${result.pin}`, '_blank');
        setSessions(prev => [result, ...prev]);
      }
    } catch (e) { alert(e.message); }
    finally { setCreating(false); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Live Games</h1>
          <p className="text-sm text-gray-500 mt-1">Kahoot-style multiplayer games in real-time</p>
        </div>
      </div>

      {/* Create game */}
      <div className="bg-white rounded-[14px] p-4 mb-6 flex items-end gap-3 flex-wrap" style={{ border: '1px solid #E7E5E4' }}>
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Assignment ID</label>
          <input value={assignmentId} onChange={e => setAssignmentId(e.target.value)} placeholder="Paste assignment UUID" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300" />
        </div>
        <div className="min-w-[180px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Game Type</label>
          <select value={shellId} onChange={e => setShellId(e.target.value)} className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none">
            {shells.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <button onClick={handleCreate} disabled={creating || !assignmentId} className="bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300 text-white px-4 py-2 rounded-xl font-medium text-sm flex items-center gap-2">
          {creating ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Play className="w-4 h-4" />}
          Create Game
        </button>
      </div>

      {/* Sessions */}
      {loading ? (
        <div className="animate-pulse space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-white/50 rounded-[14px]" />)}</div>
      ) : sessions.length === 0 ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <Gamepad2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium" style={{ fontFamily: "'DM Serif Display', serif" }}>No games yet</h3>
          <p className="text-sm text-gray-500">Create a live game from any assignment</p>
        </div>
      ) : (
        <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
          <table className="w-full text-sm">
            <thead><tr className="border-b" style={{ borderColor: '#F5F5F4' }}>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">PIN</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Game</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Status</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Created</th>
            </tr></thead>
            <tbody className="divide-y" style={{ borderColor: '#F5F5F4' }}>
              {sessions.map(s => (
                <tr key={s.session_id || s.pin} className="hover:bg-orange-50/30 transition-colors cursor-pointer" onClick={() => s.pin && window.open(`/games/${s.pin}`, '_blank')}>
                  <td className="px-4 py-3 font-mono font-bold text-orange-500 text-lg">{s.pin}</td>
                  <td className="px-4 py-3 text-gray-700">{s.game_shell_id || s.game_name}</td>
                  <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full font-medium ${s.status === 'finished' ? 'bg-green-50 text-green-700' : s.status === 'playing' ? 'bg-orange-50 text-orange-700' : 'bg-gray-100 text-gray-600'}`}>{s.status}</span></td>
                  <td className="px-4 py-3 text-xs text-gray-400">{s.created_at ? new Date(s.created_at).toLocaleString() : 'Just now'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
