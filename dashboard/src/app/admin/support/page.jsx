'use client';
import { useEffect, useState } from 'react';
import { MessageSquare, Clock, CheckCircle } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminSupport() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminFetch('/api/v1/admin/support/tickets').then(d => setTickets(d.tickets || [])).catch(console.error).finally(() => setLoading(false));
  }, []);

  const statusIcon = (s) => s === 'resolved' ? <CheckCircle className="w-3.5 h-3.5 text-green-500" /> : <Clock className="w-3.5 h-3.5 text-amber-500" />;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Support Tickets</h1>
      {!loading && tickets.length === 0 ? (
        <div className="bg-white rounded-[14px] p-8 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <MessageSquare className="w-8 h-8 text-gray-300 mx-auto mb-2" />
          <p className="text-gray-500">No support tickets</p>
        </div>
      ) : (
        <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
          <table className="w-full text-sm">
            <thead><tr className="border-b" style={{ borderColor: '#F5F5F4' }}>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Subject</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Teacher</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Priority</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Status</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Date</th>
            </tr></thead>
            <tbody className="divide-y" style={{ borderColor: '#F5F5F4' }}>
              {tickets.map(t => (
                <tr key={t.ticket_id} className="hover:bg-orange-50/30">
                  <td className="px-4 py-3 font-medium text-gray-800">{t.subject}</td>
                  <td className="px-4 py-3 text-gray-500">{t.teacher_name || t.teacher_email || '—'}</td>
                  <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full font-medium ${t.priority === 'urgent' ? 'bg-red-50 text-red-700' : t.priority === 'high' ? 'bg-amber-50 text-amber-700' : 'bg-gray-100 text-gray-600'}`}>{t.priority}</span></td>
                  <td className="px-4 py-3 flex items-center gap-1">{statusIcon(t.status)} <span className="text-xs">{t.status}</span></td>
                  <td className="px-4 py-3 text-xs text-gray-400">{t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
