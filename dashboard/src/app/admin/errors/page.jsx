'use client';
import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminErrors() {
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminFetch('/api/v1/admin/errors?limit=50')
      .then(d => setErrors(d.errors || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Error Log</h1>
      {!loading && errors.length === 0 ? (
        <div className="bg-green-50 rounded-[14px] p-8 text-center border border-green-200">
          <p className="text-green-700 font-medium">No errors — system is healthy</p>
        </div>
      ) : (
        <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
          <table className="w-full text-sm">
            <thead><tr className="border-b" style={{ borderColor: '#F5F5F4' }}>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Severity</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Type</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Message</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Time</th>
            </tr></thead>
            <tbody className="divide-y" style={{ borderColor: '#F5F5F4' }}>
              {errors.map(e => (
                <tr key={e.error_id} className="hover:bg-orange-50/30">
                  <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full font-medium ${e.severity === 'error' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'}`}>{e.severity}</span></td>
                  <td className="px-4 py-3 text-gray-600">{e.error_type}</td>
                  <td className="px-4 py-3 text-gray-800 max-w-md truncate">{e.message}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
