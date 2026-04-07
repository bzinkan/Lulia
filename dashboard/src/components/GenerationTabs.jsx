'use client';
import { useState } from 'react';
import { Sparkles, FileText, ListChecks, Loader2, AlertCircle } from 'lucide-react';
import AssignmentPicker from '@/components/AssignmentPicker';
import { apiFetch } from '@/lib/api';

const SUBJECTS = ['Mathematics', 'ELA', 'Science', 'Social Studies'];
const GRADES = ['K','1','2','3','4','5','6','7','8','9','10','11','12'];

/**
 * Reusable three-tab generation component.
 * Props:
 *   outputType: "interactive" | "game" | "video"
 *   templates: [{id, name}] — available output templates
 *   onResult: (result) => void — called when generation completes
 *   templateLabel: string — label for template selector
 */
export default function GenerationTabs({ outputType, templates = [], onResult, templateLabel = "Template" }) {
  const [tab, setTab] = useState('prompt');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  // Prompt mode
  const [prompt, setPrompt] = useState('');

  // Form mode
  const [form, setForm] = useState({ subject: 'Mathematics', grade: '4', topic: '', template: templates[0]?.id || '', questionCount: 10 });

  // Existing mode
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [existingTemplate, setExistingTemplate] = useState(templates[0]?.id || '');

  const placeholders = {
    interactive: "Create a drag-and-drop activity about the water cycle for 5th grade...",
    game: "Make a Jeopardy game about fractions for 4th grade math...",
    video: "Generate a 3-minute video lesson about equivalent fractions...",
  };

  async function handlePromptGenerate() {
    if (!prompt.trim()) return;
    setGenerating(true); setError(null);
    try {
      const result = await apiFetch('/api/v1/assistant/generate-from-prompt', {
        method: 'POST',
        body: JSON.stringify({ prompt, output_type: outputType }),
      });
      onResult(result);
    } catch (e) {
      setError(e.message?.includes('400') ? "Couldn't understand your prompt. Try being more specific." : `Generation failed: ${e.message}`);
    } finally { setGenerating(false); }
  }

  async function handleFormGenerate() {
    const fakePrompt = `Create a ${form.template || 'quiz'} about ${form.topic || form.subject} for grade ${form.grade} ${form.subject}, ${form.questionCount} questions, medium difficulty`;
    setPrompt(fakePrompt);
    setGenerating(true); setError(null);
    try {
      const result = await apiFetch('/api/v1/assistant/generate-from-prompt', {
        method: 'POST',
        body: JSON.stringify({ prompt: fakePrompt, output_type: outputType }),
      });
      onResult(result);
    } catch (e) {
      setError(`Generation failed: ${e.message}`);
    } finally { setGenerating(false); }
  }

  async function handleExistingGenerate() {
    if (!selectedAssignment) return;
    setGenerating(true); setError(null);
    try {
      let result;
      if (outputType === 'interactive') {
        result = await apiFetch('/api/v1/interactive/generate', {
          method: 'POST',
          body: JSON.stringify({ assignment_id: selectedAssignment.assignment_id, interactive_template_id: existingTemplate }),
        });
      } else if (outputType === 'game') {
        result = await apiFetch('/api/v1/games/create', {
          method: 'POST',
          body: JSON.stringify({ assignment_id: selectedAssignment.assignment_id, game_shell_id: existingTemplate }),
        });
      } else if (outputType === 'video') {
        result = await apiFetch('/api/v1/videos/generate', {
          method: 'POST',
          body: JSON.stringify({ assignment_id: selectedAssignment.assignment_id }),
        });
      }
      onResult(result);
    } catch (e) {
      setError(`Failed: ${e.message}`);
    } finally { setGenerating(false); }
  }

  return (
    <div className="bg-white rounded-[14px] p-5" style={{ border: '1px solid #E7E5E4' }}>
      {/* Tab strip */}
      <div className="flex gap-1 mb-4 p-1 rounded-xl" style={{ background: '#F5F5F4' }}>
        {[
          { id: 'prompt', label: 'Prompt', icon: Sparkles },
          { id: 'form', label: 'Quick Form', icon: ListChecks },
          { id: 'existing', label: 'From Existing', icon: FileText },
        ].map(t => (
          <button key={t.id} onClick={() => { setTab(t.id); setError(null); }}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-colors"
            style={tab === t.id ? { background: 'white', color: '#78350F', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' } : { color: '#A8A29E' }}>
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 rounded-xl flex items-start gap-2" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
          <AlertCircle className="w-4 h-4 mt-0.5" style={{ color: '#EF4444' }} />
          <div>
            <p className="text-sm" style={{ color: '#DC2626' }}>{error}</p>
            <button onClick={() => setError(null)} className="text-xs underline mt-1" style={{ color: '#EF4444' }}>Dismiss</button>
          </div>
        </div>
      )}

      {/* PROMPT TAB */}
      {tab === 'prompt' && (
        <div>
          <textarea
            value={prompt} onChange={e => setPrompt(e.target.value)}
            placeholder={placeholders[outputType] || "Describe what you want to create..."}
            rows={3}
            className="w-full rounded-xl p-3 text-sm outline-none resize-none"
            style={{ border: '1px solid #E7E5E4', fontFamily: "'DM Sans'" }}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !generating) { e.preventDefault(); handlePromptGenerate(); } }}
          />
          <button onClick={handlePromptGenerate} disabled={generating || !prompt.trim()}
            className="mt-3 w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-colors"
            style={{ background: generating ? '#FDBA74' : '#F97316', color: 'white', cursor: generating ? 'wait' : 'pointer', fontFamily: "'DM Sans'" }}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Create</>}
          </button>
        </div>
      )}

      {/* FORM TAB */}
      {tab === 'form' && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-medium mb-1" style={{ color: '#78350F' }}>Subject</label>
              <select value={form.subject} onChange={e => setForm(f => ({...f, subject: e.target.value}))} className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={{ border: '1px solid #E7E5E4' }}>
                {SUBJECTS.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-medium mb-1" style={{ color: '#78350F' }}>Grade</label>
              <select value={form.grade} onChange={e => setForm(f => ({...f, grade: e.target.value}))} className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={{ border: '1px solid #E7E5E4' }}>
                {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-medium mb-1" style={{ color: '#78350F' }}>Topic</label>
            <input value={form.topic} onChange={e => setForm(f => ({...f, topic: e.target.value}))} placeholder="e.g. equivalent fractions, water cycle" className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={{ border: '1px solid #E7E5E4' }} />
          </div>
          {templates.length > 0 && (
            <div>
              <label className="block text-[10px] font-medium mb-1" style={{ color: '#78350F' }}>{templateLabel}</label>
              <select value={form.template} onChange={e => setForm(f => ({...f, template: e.target.value}))} className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={{ border: '1px solid #E7E5E4' }}>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          )}
          <button onClick={handleFormGenerate} disabled={generating}
            className="w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2"
            style={{ background: generating ? '#FDBA74' : '#F97316', color: 'white', fontFamily: "'DM Sans'" }}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Generate</>}
          </button>
        </div>
      )}

      {/* EXISTING TAB */}
      {tab === 'existing' && (
        <div>
          <AssignmentPicker onSelect={a => setSelectedAssignment(a)} selected={selectedAssignment?.assignment_id} />
          {templates.length > 0 && selectedAssignment && (
            <div className="mt-3">
              <label className="block text-[10px] font-medium mb-1" style={{ color: '#78350F' }}>{templateLabel}</label>
              <select value={existingTemplate} onChange={e => setExistingTemplate(e.target.value)} className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={{ border: '1px solid #E7E5E4' }}>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          )}
          <button onClick={handleExistingGenerate} disabled={generating || !selectedAssignment}
            className="mt-3 w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2"
            style={{ background: (generating || !selectedAssignment) ? '#FDBA74' : '#F97316', color: 'white', fontFamily: "'DM Sans'" }}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating...</> : 'Create from Assignment'}
          </button>
        </div>
      )}
    </div>
  );
}
