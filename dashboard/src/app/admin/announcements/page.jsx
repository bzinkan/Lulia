'use client';
import { useEffect, useState } from 'react';
import { Megaphone, Plus, Trash2 } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminAnnouncements() {
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: '', message: '', type: 'info', audience: 'all' });

  useEffect(() => { load(); }, []);
  async function load() {
    adminFetch('/api/v1/admin/announcements').then(d => setAnnouncements(d.announcements || [])).catch(console.error).finally(() => setLoading(false));
  }

  async function create() {
    await adminFetch('/api/v1/admin/announcements', { method: 'POST', body: JSON.stringify(form) });
    setShowCreate(false);
    setForm({ title: '', message: '', type: 'info', audience: 'all' });
    load();
  }

  async function remove(id) {
    await adminFetch(`/api/v1/admin/announcements/${id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Announcements</h1>
        <button onClick={() => setShowCreate(!showCreate)} className="bg-orange-500 hover:bg-orange-600 text-white px-3 py-1.5 rounded-xl text-sm font-medium flex items-center gap-1">
          <Plus className="w-4 h-4" /> New
        </button>
      </div>

      {showCreate && (
        <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
          <div className="space-y-3">
            <input value={form.title} onChange={e => setForm(f => ({...f, title: e.target.value}))} placeholder="Title" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none" />
            <textarea value={form.message} onChange={e => setForm(f => ({...f, message: e.target.value}))} placeholder="Message" rows={3} className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none" />
            <div className="flex gap-2">
              {['info', 'warning', 'success', 'marketing'].map(t => (
                <button key={t} onClick={() => setForm(f => ({...f, type: t}))} className={`text-xs px-2 py-1 rounded-lg ${form.type === t ? 'bg-orange-500 text-white' : 'bg-gray-100 text-gray-600'}`}>{t}</button>
              ))}
            </div>
            <button onClick={create} className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl text-sm font-medium">Publish</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {announcements.map(a => (
          <div key={a.announcement_id} className="bg-white rounded-[14px] p-4 flex items-center justify-between" style={{ border: '1px solid #E7E5E4' }}>
            <div>
              <div className="flex items-center gap-2">
                <Megaphone className="w-4 h-4 text-orange-400" />
                <span className="text-sm font-medium text-gray-800">{a.title}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded ${a.type === 'warning' ? 'bg-amber-50 text-amber-700' : a.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-blue-50 text-blue-700'}`}>{a.type}</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">{a.message?.slice(0, 100)}</p>
            </div>
            <button onClick={() => remove(a.announcement_id)} className="text-gray-400 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
