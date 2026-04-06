'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Search, Users } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminTeachers() {
  const [teachers, setTeachers] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, [search]);

  async function load() {
    try {
      const q = search ? `?search=${encodeURIComponent(search)}` : '';
      const data = await adminFetch(`/api/v1/admin/teachers${q}`);
      setTeachers(data.teachers || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Teachers</h1>
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search teachers..." className="pl-9 pr-4 py-2 border border-gray-200 rounded-xl text-sm bg-white outline-none focus:ring-2 focus:ring-orange-300 w-64" />
        </div>
      </div>

      <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b" style={{ borderColor: '#F5F5F4' }}>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Name</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Email</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">State</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Generations</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">KB Sources</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Joined</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: '#F5F5F4' }}>
            {loading ? (
              [1,2,3].map(i => <tr key={i}><td colSpan={6} className="px-4 py-3"><div className="h-4 bg-gray-100 rounded animate-pulse" /></td></tr>)
            ) : teachers.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-400">No teachers found</td></tr>
            ) : teachers.map(t => (
              <tr key={t.teacher_id} className="hover:bg-orange-50/30 transition-colors cursor-pointer" onClick={() => window.location.href = `/admin/teachers/${t.teacher_id}`}>
                <td className="px-4 py-3 font-medium text-gray-800">{t.name}</td>
                <td className="px-4 py-3 text-gray-500">{t.email}</td>
                <td className="px-4 py-3 text-gray-500">{t.state_code || '—'}</td>
                <td className="px-4 py-3"><span className="text-orange-600 font-semibold">{t.total_generations}</span></td>
                <td className="px-4 py-3 text-gray-500">{t.kb_sources}</td>
                <td className="px-4 py-3 text-xs text-gray-400">{t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
