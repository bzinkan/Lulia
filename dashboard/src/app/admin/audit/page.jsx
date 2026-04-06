'use client';
import { useEffect, useState } from 'react';
import { FileText } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminAudit() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminFetch('/api/v1/admin/audit?limit=100')
      .then(d => setLogs(d.audit_log || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Admin Audit Log</h1>
      <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
        {!loading && logs.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No audit entries yet</div>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b" style={{ borderColor: '#F5F5F4' }}>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Admin</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Action</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Target</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Time</th>
            </tr></thead>
            <tbody className="divide-y" style={{ borderColor: '#F5F5F4' }}>
              {logs.map(l => (
                <tr key={l.log_id} className={`hover:bg-orange-50/30 ${l.action.includes('impersonate') ? 'bg-amber-50/50' : ''}`}>
                  <td className="px-4 py-3 text-gray-800">{l.admin_email}</td>
                  <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full font-medium ${l.action.includes('impersonate') ? 'bg-amber-100 text-amber-700' : l.action.includes('suspend') ? 'bg-red-50 text-red-700' : 'bg-gray-100 text-gray-600'}`}>{l.action}</span></td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{l.target_type ? `${l.target_type}: ${l.target_id?.slice(0, 8)}...` : '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{l.created_at ? new Date(l.created_at).toLocaleString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
