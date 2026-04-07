'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Palette, Plus, Copy, Trash2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function DesignTemplates() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      const data = await apiFetch('/api/v1/design/templates');
      setTemplates(data.templates || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function handleDuplicate(id) {
    await apiFetch(`/api/v1/design/templates/${id}/duplicate`, { method: 'POST' });
    load();
  }

  async function handleDelete(id) {
    if (!confirm('Delete this template?')) return;
    await apiFetch(`/api/v1/design/templates/${id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>My Templates</h1>
          <p className="text-sm text-gray-500 mt-1">Custom templates you've designed</p>
        </div>
        <Link href="/design" className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-medium text-sm flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Template
        </Link>
      </div>

      {loading ? (
        <div className="animate-pulse grid grid-cols-2 md:grid-cols-3 gap-4">{[1,2,3].map(i => <div key={i} className="h-40 bg-white/50 rounded-[14px]" />)}</div>
      ) : templates.length === 0 ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <Palette className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium" style={{ fontFamily: "'DM Serif Display', serif" }}>No custom templates yet</h3>
          <p className="text-sm text-gray-500 mb-4">Design your own worksheet templates with the drag-and-drop builder</p>
          <Link href="/design" className="inline-flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-medium text-sm">
            <Plus className="w-4 h-4" /> Create Template
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map(t => (
            <div key={t.template_id} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
              <div className="flex items-start justify-between mb-2">
                <div>
                  <p className="text-sm font-medium text-gray-800">{t.name}</p>
                  <p className="text-xs text-gray-400">{t.category?.replace('_', ' ')}</p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-50 text-orange-700 border border-orange-200">{t.usage_count} uses</span>
              </div>
              {t.description && <p className="text-xs text-gray-500 mb-3">{t.description}</p>}
              <div className="flex gap-2">
                <Link href={`/design?template=${t.template_id}`} className="flex-1 text-center text-xs py-1.5 rounded-lg bg-orange-50 text-orange-700 hover:bg-orange-100 font-medium">Edit</Link>
                <button onClick={() => handleDuplicate(t.template_id)} className="px-2 py-1.5 rounded-lg bg-gray-50 text-gray-500 hover:bg-gray-100"><Copy className="w-3.5 h-3.5" /></button>
                <button onClick={() => handleDelete(t.template_id)} className="px-2 py-1.5 rounded-lg bg-gray-50 text-red-500 hover:bg-red-50"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
