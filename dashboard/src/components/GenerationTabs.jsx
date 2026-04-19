'use client';
import { useState } from 'react';
import { Sparkles, FileText, ListChecks, Target, Loader2, AlertCircle } from 'lucide-react';
import AssignmentPicker from '@/components/AssignmentPicker';
import StandardsPickerModal from '@/components/StandardsPickerModal';
import { apiFetch } from '@/lib/api';

const SUBJECTS = ['Mathematics', 'ELA', 'Science', 'Social Studies'];
const GRADES = ['K','1','2','3','4','5','6','7','8','9','10','11','12'];

/**
 * Reusable four-tab generation component — Retro Earth palette.
 *
 * Props:
 *   outputType: "interactive" | "game" | "video" | "slides"
 *   templates: [{id, name}] — available output templates
 *   onResult: (result) => void — called when generation completes
 *   templateLabel: string — label for template selector
 *   activeClass: {name, subject, grade_level} — optional. When provided,
 *     Subject/Grade fields are hidden and values are sourced from the class.
 */
export default function GenerationTabs({ outputType, templates = [], onResult, templateLabel = "Template", activeClass = null }) {
  const [tab, setTab] = useState('prompt');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  // Class-scoped defaults (when the page is inside a class tab)
  const classSubject = activeClass?.subject || null;
  const classGrade = activeClass?.grade_level || null;

  // Prompt mode
  const [prompt, setPrompt] = useState('');

  // Form mode
  const [form, setForm] = useState({
    subject: classSubject || 'Mathematics',
    grade: classGrade || '4',
    topic: '',
    template: templates[0]?.id || '',
    questionCount: 10,
  });

  // Existing mode
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [existingTemplate, setExistingTemplate] = useState(templates[0]?.id || '');

  // Standards mode
  const [showStandardsPicker, setShowStandardsPicker] = useState(false);
  const [standardsCodes, setStandardsCodes] = useState([]); // string[]
  const [standardsForm, setStandardsForm] = useState({
    grade: classGrade || '4',
    subject: classSubject || 'Mathematics',
    template: templates[0]?.id || '',
  });

  const placeholders = {
    interactive: 'Create a drag-and-drop activity about the water cycle for 5th grade...',
    game: 'Make a Jeopardy game about fractions for 4th grade math...',
    video: 'Generate a 3-minute video lesson about equivalent fractions...',
    slides: 'A 10-slide introduction to photosynthesis for 6th grade...',
  };

  const inputBase = {
    border: '1px solid var(--border)', background: 'white',
    color: 'var(--text-dark)', fontFamily: "'Nunito', sans-serif",
  };

  async function handlePromptGenerate() {
    if (!prompt.trim()) return;
    setGenerating(true); setError(null);
    try {
      const result = await apiFetch('/api/v1/assistant/generate-from-prompt', {
        method: 'POST',
        body: JSON.stringify({
          prompt,
          output_type: outputType,
          class_id: activeClass?.class_id,
        }),
      });
      onResult(result);
    } catch (e) {
      setError(e.message?.includes('400')
        ? "Couldn't understand your prompt. Try being more specific."
        : `Generation failed: ${e.message}`);
    } finally { setGenerating(false); }
  }

  async function handleFormGenerate() {
    // Class context is authoritative when present
    const effSubject = classSubject || form.subject;
    const effGrade = classGrade || form.grade;
    const fakePrompt = `Create a ${form.template || 'quiz'} about ${form.topic || effSubject} for grade ${effGrade} ${effSubject}, ${form.questionCount} questions, medium difficulty`;
    setPrompt(fakePrompt);
    setGenerating(true); setError(null);
    try {
      const result = await apiFetch('/api/v1/assistant/generate-from-prompt', {
        method: 'POST',
        body: JSON.stringify({
          prompt: fakePrompt,
          output_type: outputType,
          class_id: activeClass?.class_id,
        }),
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

  async function handleStandardsGenerate() {
    if (standardsCodes.length === 0) {
      setError('Pick at least one standard first.');
      return;
    }
    const effSubject = classSubject || standardsForm.subject;
    const effGrade = classGrade || standardsForm.grade;
    const synth = `Create a ${standardsForm.template || 'quiz'} for Grade ${effGrade} ${effSubject}, covering standards: ${standardsCodes.join(', ')}. 10 questions, medium difficulty, standards-aligned.`;
    setPrompt(synth);
    setGenerating(true); setError(null);
    try {
      const result = await apiFetch('/api/v1/assistant/generate-from-prompt', {
        method: 'POST',
        body: JSON.stringify({
          prompt: synth,
          output_type: outputType,
          class_id: activeClass?.class_id,
        }),
      });
      onResult(result);
    } catch (e) {
      setError(`Generation failed: ${e.message}`);
    } finally { setGenerating(false); }
  }

  const primaryBtn = (disabled) => ({
    background: disabled ? 'var(--coral-light)' : 'var(--coral)',
    color: 'white',
    fontFamily: "'Nunito', sans-serif",
    boxShadow: disabled ? 'none' : '0 3px 12px rgba(216, 108, 82, 0.3)',
    cursor: disabled ? 'wait' : 'pointer',
  });

  return (
    <div className="rounded-[14px] p-5"
      style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
      {/* Class context banner — shown when we know the active class */}
      {activeClass && (
        <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-xl text-[12px]"
          style={{
            background: 'rgba(107,160,138,0.1)',
            border: '1px solid rgba(107,160,138,0.3)',
            color: 'var(--text-dark)',
          }}>
          <span className="font-bold uppercase tracking-wider text-[10px]"
            style={{ color: 'var(--sage)' }}>
            Generating for
          </span>
          <span className="font-semibold">{activeClass.name}</span>
          <span style={{ color: 'var(--text-light)' }}>·</span>
          <span style={{ color: 'var(--text-mid)' }}>
            Grade {activeClass.grade_level} {activeClass.subject}
          </span>
        </div>
      )}

      {/* Tab strip */}
      <div className="flex gap-1 mb-4 p-1 rounded-xl" style={{ background: 'var(--cream)' }}>
        {[
          { id: 'prompt',    label: 'Prompt',        icon: Sparkles },
          { id: 'form',      label: 'Quick Form',    icon: ListChecks },
          { id: 'standards', label: 'From Standards', icon: Target },
          { id: 'existing',  label: 'From Existing', icon: FileText },
        ].map(t => {
          const active = tab === t.id;
          return (
            <button key={t.id} onClick={() => { setTab(t.id); setError(null); }}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-colors"
              style={active
                ? { background: 'white', color: 'var(--coral)', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }
                : { color: 'var(--text-mid)', background: 'transparent' }}>
              <t.icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 rounded-xl flex items-start gap-2"
          style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #FECACA' }}>
          <AlertCircle className="w-4 h-4 mt-0.5" style={{ color: '#EF4444' }} />
          <div>
            <p className="text-sm" style={{ color: '#B91C1C' }}>{error}</p>
            <button onClick={() => setError(null)} className="text-xs underline mt-1" style={{ color: '#EF4444' }}>Dismiss</button>
          </div>
        </div>
      )}

      {/* PROMPT TAB */}
      {tab === 'prompt' && (
        <div>
          <textarea
            value={prompt} onChange={e => setPrompt(e.target.value)}
            placeholder={placeholders[outputType] || 'Describe what you want to create...'}
            rows={3}
            className="w-full rounded-xl p-3 text-sm outline-none resize-none"
            style={inputBase}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !generating) { e.preventDefault(); handlePromptGenerate(); } }}
          />
          <button onClick={handlePromptGenerate} disabled={generating || !prompt.trim()}
            className="mt-3 w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2"
            style={primaryBtn(generating || !prompt.trim())}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Create</>}
          </button>
        </div>
      )}

      {/* FORM TAB */}
      {tab === 'form' && (
        <div className="space-y-3">
          {!activeClass && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>Subject</label>
                <select value={form.subject} onChange={e => setForm(f => ({...f, subject: e.target.value}))}
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={inputBase}>
                  {SUBJECTS.map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>Grade</label>
                <select value={form.grade} onChange={e => setForm(f => ({...f, grade: e.target.value}))}
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={inputBase}>
                  {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
                </select>
              </div>
            </div>
          )}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>Topic</label>
            <input value={form.topic} onChange={e => setForm(f => ({...f, topic: e.target.value}))}
              placeholder="e.g. equivalent fractions, water cycle"
              className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={inputBase} />
          </div>
          {templates.length > 0 && (
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>{templateLabel}</label>
              <select value={form.template} onChange={e => setForm(f => ({...f, template: e.target.value}))}
                className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={inputBase}>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          )}
          <button onClick={handleFormGenerate} disabled={generating}
            className="w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2"
            style={primaryBtn(generating)}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Generate</>}
          </button>
        </div>
      )}

      {/* FROM STANDARDS TAB */}
      {tab === 'standards' && (
        <div className="space-y-3">
          {!activeClass && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>Subject</label>
                <select value={standardsForm.subject} onChange={e => setStandardsForm(f => ({...f, subject: e.target.value}))}
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={inputBase}>
                  {SUBJECTS.map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>Grade</label>
                <select value={standardsForm.grade} onChange={e => setStandardsForm(f => ({...f, grade: e.target.value}))}
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={inputBase}>
                  {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
                </select>
              </div>
            </div>
          )}

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>Standards</label>
            <div className="flex flex-wrap gap-2 items-center">
              {standardsCodes.map(code => (
                <span key={code} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-bold"
                  style={{ background: 'rgba(78,140,150,0.12)', color: 'var(--teal, #4E8C96)' }}>
                  {code}
                  <button onClick={() => setStandardsCodes(prev => prev.filter(c => c !== code))}
                    style={{ color: 'var(--teal)', fontSize: 14, lineHeight: 1, cursor: 'pointer' }}>×</button>
                </span>
              ))}
              <button onClick={() => setShowStandardsPicker(true)}
                className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl"
                style={{ border: '1px dashed var(--border)', background: 'white', color: 'var(--text-mid)', cursor: 'pointer' }}>
                <Target className="w-3.5 h-3.5" /> {standardsCodes.length ? 'Add another' : 'Pick a standard'}
              </button>
            </div>
          </div>

          {templates.length > 0 && (
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>{templateLabel}</label>
              <select value={standardsForm.template} onChange={e => setStandardsForm(f => ({...f, template: e.target.value}))}
                className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={inputBase}>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          )}

          <button onClick={handleStandardsGenerate} disabled={generating || standardsCodes.length === 0}
            className="w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2"
            style={primaryBtn(generating || standardsCodes.length === 0)}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Target className="w-4 h-4" /> Generate from standards</>}
          </button>
        </div>
      )}

      {/* EXISTING TAB */}
      {tab === 'existing' && (
        <div>
          <AssignmentPicker onSelect={a => setSelectedAssignment(a)} selected={selectedAssignment?.assignment_id} />
          {templates.length > 0 && selectedAssignment && (
            <div className="mt-3">
              <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-mid)' }}>{templateLabel}</label>
              <select value={existingTemplate} onChange={e => setExistingTemplate(e.target.value)}
                className="w-full rounded-xl px-3 py-2 text-sm outline-none" style={inputBase}>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          )}
          <button onClick={handleExistingGenerate} disabled={generating || !selectedAssignment}
            className="mt-3 w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2"
            style={primaryBtn(generating || !selectedAssignment)}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating...</> : 'Create from Assignment'}
          </button>
        </div>
      )}

      {showStandardsPicker && (
        <StandardsPickerModal
          subject={classSubject || standardsForm.subject}
          gradeLevel={classGrade || standardsForm.grade}
          stateCode={activeClass?.state_code}
          initialSelected={standardsCodes}
          onConfirm={(codes) => {
            setStandardsCodes(codes);
            setShowStandardsPicker(false);
          }}
          onClose={() => setShowStandardsPicker(false)} />
      )}
    </div>
  );
}
