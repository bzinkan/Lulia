'use client';
import { useEffect, useState } from 'react';
import { Gamepad2, Copy, Users, ExternalLink, Plus, Trash2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function InteractivePage() {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [assignmentId, setAssignmentId] = useState('');
  const [templateId, setTemplateId] = useState('multiple_choice_quiz');
  const [templates, setTemplates] = useState([]);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/interactive').then(d => setActivities(d.activities || [])),
      apiFetch('/api/v1/interactive/templates').then(d => setTemplates(d.templates || [])),
    ]).catch(console.error).finally(() => setLoading(false));
  }, []);

  async function handleGenerate() {
    if (!assignmentId) return;
    setGenerating(true);
    try {
      const result = await apiFetch('/api/v1/interactive/generate', {
        method: 'POST',
        body: JSON.stringify({ assignment_id: assignmentId, interactive_template_id: templateId }),
      });
      setActivities(prev => [result, ...prev]);
      setAssignmentId('');
    } catch (e) { alert(e.message); }
    finally { setGenerating(false); }
  }

  function copyCode(code) {
    navigator.clipboard?.writeText(code);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Interactive Activities</h1>
          <p className="text-sm text-gray-500 mt-1">Web-based student activities with instant feedback</p>
        </div>
      </div>

      {/* Quick generate */}
      <div className="bg-white rounded-[14px] p-4 mb-6 flex items-end gap-3 flex-wrap" style={{ border: '1px solid #E7E5E4' }}>
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Assignment ID</label>
          <input value={assignmentId} onChange={e => setAssignmentId(e.target.value)} placeholder="Paste assignment UUID" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300" />
        </div>
        <div className="min-w-[180px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Template</label>
          <select value={templateId} onChange={e => setTemplateId(e.target.value)} className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none">
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <button onClick={handleGenerate} disabled={generating || !assignmentId} className="bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300 text-white px-4 py-2 rounded-xl font-medium text-sm flex items-center gap-2">
          {generating ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Plus className="w-4 h-4" />}
          Create Activity
        </button>
      </div>

      {/* Activities grid */}
      {loading ? (
        <div className="animate-pulse grid grid-cols-2 md:grid-cols-3 gap-4">{[1,2,3].map(i => <div key={i} className="h-40 bg-white/50 rounded-[14px]" />)}</div>
      ) : activities.length === 0 ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <Gamepad2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium" style={{ fontFamily: "'DM Serif Display', serif" }}>No activities yet</h3>
          <p className="text-sm text-gray-500">Create an interactive activity from any assignment</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {activities.map(a => (
            <div key={a.activity_id} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
              <div className="flex items-start justify-between mb-2">
                <span className="text-xs font-medium uppercase text-orange-500">{a.interactive_template_id?.replace(/_/g, ' ')}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${a.status === 'live' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'}`}>{a.status}</span>
              </div>
              <p className="text-sm font-medium text-gray-800 mb-2">{a.content_json?.title || 'Activity'}</p>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded text-gray-700">{a.access_code}</span>
                <button onClick={() => copyCode(a.access_code)} className="text-gray-400 hover:text-orange-500"><Copy className="w-3.5 h-3.5" /></button>
                {a.access_url && (
                  <a href={a.access_url} target="_blank" rel="noopener" className="text-gray-400 hover:text-orange-500"><ExternalLink className="w-3.5 h-3.5" /></a>
                )}
              </div>
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span className="flex items-center gap-1"><Users className="w-3 h-3" /> {a.submission_count || 0} submissions</span>
                <span>{a.created_at ? new Date(a.created_at).toLocaleDateString() : ''}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
