'use client';
import { useEffect, useState } from 'react';
import { Shield, Plus, Trash2, CheckCircle } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const TYPE_COLORS = {
  iep: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  '504': { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  ell: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  gifted: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  custom: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
};

export default function AccommodationsPage() {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', type: 'custom', modifications: {} });

  useEffect(() => { loadProfiles(); }, []);

  async function loadProfiles() {
    try {
      const data = await apiFetch('/api/v1/accommodations/profiles');
      setProfiles(data.profiles || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function handleCreate() {
    await apiFetch('/api/v1/accommodations/profiles', {
      method: 'POST',
      body: JSON.stringify(form),
    });
    setShowCreate(false);
    setForm({ name: '', type: 'custom', modifications: {} });
    loadProfiles();
  }

  async function handleDelete(id) {
    await apiFetch(`/api/v1/accommodations/profiles/${id}`, { method: 'DELETE' });
    loadProfiles();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Accommodations</h1>
          <p className="text-sm text-gray-500 mt-1">Manage IEP/504/ELL/Gifted profiles — all versions use the same beautiful design</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-medium text-sm transition-colors flex items-center gap-2"
        >
          <Plus className="w-4 h-4" /> New Profile
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
          <h2 className="text-lg font-semibold text-gray-900 mb-4" style={{ fontFamily: "'DM Serif Display', serif" }}>Create Custom Profile</h2>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Profile Name</label>
              <input value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300" placeholder="e.g. IEP — Reduced with Visuals" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
              <select value={form.type} onChange={e => setForm(f => ({...f, type: e.target.value}))} className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none">
                {['iep', '504', 'ell', 'gifted', 'custom'].map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
              </select>
            </div>
          </div>
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 mb-2">Modifications</label>
            <div className="grid grid-cols-2 gap-2">
              {['simplify_language', 'visual_supports', 'vocabulary_glossary', 'sentence_starters', 'larger_font', 'extra_answer_space', 'checklist_format', 'increase_difficulty', 'real_world_application'].map(mod => (
                <label key={mod} className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={!!form.modifications[mod]} onChange={e => setForm(f => ({...f, modifications: {...f.modifications, [mod]: e.target.checked || undefined}}))} className="accent-orange-500" />
                  {mod.replace(/_/g, ' ')}
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={handleCreate} className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-medium text-sm">Create</button>
            <button onClick={() => setShowCreate(false)} className="bg-white hover:bg-gray-50 text-gray-600 border border-gray-200 px-4 py-2 rounded-xl font-medium text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Profiles grid */}
      {loading ? (
        <div className="animate-pulse space-y-3">{[1,2,3].map(i => <div key={i} className="h-20 bg-gray-200 rounded-[14px]" />)}</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {profiles.map(p => {
            const colors = TYPE_COLORS[p.type] || TYPE_COLORS.custom;
            const mods = p.modifications || {};
            return (
              <div key={p.profile_id} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-orange-500" />
                    <span className="font-medium text-sm text-gray-800">{p.name}</span>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${colors.bg} ${colors.text} border ${colors.border}`}>
                    {p.type?.toUpperCase()}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 mb-3">
                  {Object.keys(mods).filter(k => mods[k] && k !== 'font_size_min' && k !== 'grade_level_adjust' && k !== 'reduce_answer_choices' && k !== 'depth_of_knowledge' && k !== 'add_extension_questions' && k !== 'reduce_questions_pct').map(k => (
                    <span key={k} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{k.replace(/_/g, ' ')}</span>
                  ))}
                  {mods.reduce_questions_pct && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-50 text-red-600">-{mods.reduce_questions_pct}% questions</span>}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-gray-400">{p.is_default ? 'Built-in' : 'Custom'}</span>
                  {!p.is_default && (
                    <button onClick={() => handleDelete(p.profile_id)} className="text-gray-400 hover:text-red-500 transition-colors">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
