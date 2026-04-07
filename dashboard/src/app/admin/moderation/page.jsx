'use client';
import { useEffect, useState } from 'react';
import { Flag, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminModeration() {
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);
  async function load() {
    adminFetch('/api/v1/admin/moderation/queue').then(d => setFlags(d.flags || [])).catch(console.error).finally(() => setLoading(false));
  }

  async function handleAction(flagId, action) {
    await adminFetch(`/api/v1/admin/moderation/${flagId}/${action}`, { method: 'POST', body: JSON.stringify({ notes: '' }) });
    load();
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Content Moderation</h1>
      {!loading && flags.length === 0 ? (
        <div className="bg-green-50 rounded-[14px] p-8 text-center border border-green-200">
          <CheckCircle className="w-8 h-8 text-green-400 mx-auto mb-2" />
          <p className="text-green-700 font-medium">Queue is clear — no pending flags</p>
        </div>
      ) : (
        <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
          <table className="w-full text-sm">
            <thead><tr className="border-b" style={{ borderColor: '#F5F5F4' }}>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Type</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Reason</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Date</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Actions</th>
            </tr></thead>
            <tbody className="divide-y" style={{ borderColor: '#F5F5F4' }}>
              {flags.map(f => (
                <tr key={f.flag_id}>
                  <td className="px-4 py-3 text-gray-700">{f.content_type}</td>
                  <td className="px-4 py-3"><span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700">{f.reason}</span></td>
                  <td className="px-4 py-3 text-xs text-gray-400">{f.created_at ? new Date(f.created_at).toLocaleDateString() : ''}</td>
                  <td className="px-4 py-3 flex gap-1">
                    <button onClick={() => handleAction(f.flag_id, 'dismiss')} className="text-xs px-2 py-1 rounded bg-green-50 text-green-700 hover:bg-green-100">Dismiss</button>
                    <button onClick={() => handleAction(f.flag_id, 'remove')} className="text-xs px-2 py-1 rounded bg-red-50 text-red-700 hover:bg-red-100">Remove</button>
                    <button onClick={() => handleAction(f.flag_id, 'warn')} className="text-xs px-2 py-1 rounded bg-amber-50 text-amber-700 hover:bg-amber-100">Warn</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
