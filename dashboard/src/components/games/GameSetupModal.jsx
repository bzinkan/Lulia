'use client';
import { useEffect, useState } from 'react';
import Image from 'next/image';
import { X, Play, Loader2, FileText, Bookmark, Sparkles, Info } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { BASE_SETTINGS } from '@/lib/gameShellConfigs';
import StandardsPickerModal from '@/components/StandardsPickerModal';
import { useClassContext } from '@/components/ClassContext';

const SOURCE_TABS = [
  { id: 'assignment', label: 'From Assignment', desc: 'Reuse a worksheet you already made', icon: FileText, free: true },
  { id: 'standards',  label: 'From Standards',  desc: 'Pull questions from assignments tagged to specific standards', icon: Bookmark, free: true },
  { id: 'custom',     label: 'Describe Topic',  desc: 'Generate fresh questions from a prompt', icon: Sparkles, free: false, credits: 2 },
];

export default function GameSetupModal({ shell, teacherId, classId, onLaunched, onClose }) {
  const { classes } = useClassContext();
  const activeClass = classes.find(c => c.class_id === classId);

  const [source, setSource] = useState('assignment');
  const [assignments, setAssignments] = useState([]);
  const [assignmentId, setAssignmentId] = useState('');
  const [standards, setStandards] = useState([]);
  const [showStandardsPicker, setShowStandardsPicker] = useState(false);
  const [prompt, setPrompt] = useState('');

  // Settings — merge base + shell-specific
  const allSettings = [...BASE_SETTINGS, ...(shell.extra_settings || [])];
  const initial = allSettings.reduce((acc, f) => { acc[f.key] = f.default; return acc; }, {});
  const [settings, setSettings] = useState(initial);

  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Load teacher's assignments once
    apiFetch(`/api/v1/assignments?teacher_id=${teacherId}&limit=50`)
      .then(d => setAssignments(d.assignments || d.items || d || []))
      .catch(() => setAssignments([]));
  }, [teacherId]);

  async function handleLaunch() {
    setError(null);

    // Build question_source payload
    let questionSource;
    if (source === 'assignment') {
      if (!assignmentId) { setError('Pick an assignment first.'); return; }
      questionSource = { type: 'assignment', assignment_id: assignmentId };
    } else if (source === 'standards') {
      if (standards.length === 0) { setError('Pick at least one standard.'); return; }
      questionSource = { type: 'standards', standards, question_count: settings.question_count };
    } else if (source === 'custom') {
      if (!prompt.trim() || prompt.trim().length < 10) { setError('Describe the topic (at least 10 characters).'); return; }
      questionSource = { type: 'custom', prompt: prompt.trim(), question_count: settings.question_count };
    }

    setLaunching(true);
    try {
      const result = await apiFetch('/api/v1/games/create', {
        method: 'POST',
        body: JSON.stringify({
          game_shell_id: shell.id,
          teacher_id: teacherId,
          class_id: classId || null,
          question_source: questionSource,
          settings,
        }),
      });
      if (result.error) {
        setError(result.error);
      } else {
        onLaunched?.(result);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLaunching(false);
    }
  }

  const selectedTab = SOURCE_TABS.find(t => t.id === source);
  const willChargeCredits = source === 'custom';

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-xl mx-4 max-h-[92vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-3">
            <ShellIcon shell={shell} />
            <div>
              <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>{shell.name}</h3>
              <p className="text-[11px]" style={{ color: 'var(--text-light)' }}>{shell.desc}</p>
            </div>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-light)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Source tabs */}
          <div>
            <label className="block text-[11px] font-bold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
              Question source
            </label>
            <div className="grid grid-cols-3 gap-2">
              {SOURCE_TABS.map(t => {
                const active = source === t.id;
                const Icon = t.icon;
                return (
                  <button key={t.id} onClick={() => setSource(t.id)}
                    className="p-2.5 rounded-xl text-left"
                    style={{
                      background: active ? 'rgba(107,160,138,0.1)' : 'var(--cream)',
                      border: `2px solid ${active ? 'var(--sage)' : 'var(--border)'}`,
                      cursor: 'pointer',
                    }}>
                    <Icon className="w-4 h-4 mb-1" style={{ color: active ? 'var(--sage)' : 'var(--text-mid)' }} />
                    <div className="text-[12px] font-bold" style={{ color: 'var(--text-dark)' }}>{t.label}</div>
                    <div className="text-[10px]" style={{ color: 'var(--text-light)' }}>
                      {t.free ? 'Free' : `${t.credits} credits`}
                    </div>
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] mt-1.5" style={{ color: 'var(--text-light)' }}>
              {selectedTab?.desc}
            </p>
          </div>

          {/* Source body */}
          {source === 'assignment' && (
            <div>
              <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
                Pick an assignment
              </label>
              <select value={assignmentId} onChange={e => setAssignmentId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl text-[13px]"
                style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}>
                <option value="">-- select --</option>
                {assignments.map(a => (
                  <option key={a.assignment_id} value={a.assignment_id}>
                    {a.title} {a.output_template_id ? `(${a.output_template_id})` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          {source === 'standards' && (
            <div>
              <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
                Standards to cover
              </label>
              {standards.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {standards.map(s => (
                    <span key={s} className="text-[11px] px-2 py-1 rounded-full font-semibold"
                      style={{ background: 'rgba(216,108,82,0.12)', color: 'var(--coral)', border: '1px solid var(--coral)' }}>
                      {s}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] italic mb-2" style={{ color: 'var(--text-light)' }}>
                  None selected yet.
                </p>
              )}
              <button onClick={() => setShowStandardsPicker(true)}
                className="text-[12px] font-semibold px-3 py-1.5 rounded-lg"
                style={{ color: 'var(--coral)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                {standards.length === 0 ? 'Pick standards' : 'Change standards'}
              </button>
              <div className="mt-2 p-2.5 rounded-lg flex items-start gap-2 text-[11px]"
                style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)', color: 'var(--text-mid)' }}>
                <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#3B82F6' }} />
                <span>
                  We pull questions from assignments you've already made that cover these standards.
                  If there's no match, switch to <strong>Describe Topic</strong>.
                </span>
              </div>
            </div>
          )}

          {source === 'custom' && (
            <div>
              <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
                Describe the topic
              </label>
              <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
                rows={3}
                placeholder="e.g. Multiplication facts 6×7 to 9×9 for 4th grade"
                className="w-full px-3 py-2 rounded-xl text-[13px]"
                style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }} />
              <p className="text-[11px] mt-1" style={{ color: 'var(--text-light)' }}>
                Be specific — Lulia will generate {settings.question_count} questions with real distractors.
              </p>
            </div>
          )}

          {/* Settings */}
          <div>
            <label className="block text-[11px] font-bold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
              Game settings
            </label>
            <div className="space-y-2.5">
              {allSettings.map(f => (
                <SettingField key={f.key} field={f} value={settings[f.key]}
                  onChange={v => setSettings({ ...settings, [f.key]: v })} />
              ))}
            </div>
          </div>

          {error && (
            <div className="p-2.5 rounded-lg text-[12px]"
              style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444', color: '#EF4444' }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-5 flex items-center justify-between" style={{ borderTop: '1px solid var(--border)' }}>
          <span className="text-[12px] font-bold px-2.5 py-1 rounded-full"
            style={willChargeCredits
              ? { background: 'rgba(216,108,82,0.12)', color: 'var(--coral)' }
              : { background: 'rgba(107,160,138,0.12)', color: 'var(--sage)' }}>
            {willChargeCredits ? `${selectedTab.credits} credits` : 'Free'}
          </span>
          <div className="flex gap-2">
            <button onClick={onClose}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold"
              style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
              Cancel
            </button>
            <button onClick={handleLaunch} disabled={launching}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white flex items-center gap-2 disabled:opacity-50"
              style={{ background: 'var(--coral)' }}>
              {launching
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Launching…</>
                : <><Play className="w-4 h-4" /> Launch Game</>}
            </button>
          </div>
        </div>

        {showStandardsPicker && (
          <StandardsPickerModal
            subject={activeClass?.subject || ''}
            gradeLevel={activeClass?.grade_level || ''}
            stateCode="OH"
            initialSelected={standards}
            onConfirm={(codes) => { setStandards(codes); setShowStandardsPicker(false); }}
            onClose={() => setShowStandardsPicker(false)}
          />
        )}
      </div>
    </div>
  );
}

function SettingField({ field, value, onChange }) {
  if (field.type === 'number') {
    return (
      <div className="flex items-center justify-between gap-3">
        <label className="text-[12px] font-semibold flex-1" style={{ color: 'var(--text-dark)' }}>{field.label}</label>
        <input type="number" min={field.min} max={field.max} value={value}
          onChange={e => onChange(parseInt(e.target.value) || field.default)}
          className="w-24 px-2 py-1 rounded-lg text-[12px] text-right"
          style={{ border: '1px solid var(--border)', background: 'white' }} />
      </div>
    );
  }
  if (field.type === 'select') {
    return (
      <div className="flex items-center justify-between gap-3">
        <label className="text-[12px] font-semibold flex-1" style={{ color: 'var(--text-dark)' }}>{field.label}</label>
        <select value={value} onChange={e => onChange(isNaN(+e.target.value) ? e.target.value : +e.target.value)}
          className="px-2 py-1 rounded-lg text-[12px]"
          style={{ border: '1px solid var(--border)', background: 'white' }}>
          {field.options.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
      </div>
    );
  }
  if (field.type === 'toggle') {
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)}
          style={{ accentColor: 'var(--coral)' }} />
        <span className="text-[12px] font-semibold" style={{ color: 'var(--text-dark)' }}>{field.label}</span>
      </label>
    );
  }
  if (field.type === 'text') {
    return (
      <div>
        <label className="text-[12px] font-semibold mb-1 block" style={{ color: 'var(--text-dark)' }}>{field.label}</label>
        <input value={value || ''} onChange={e => onChange(e.target.value)}
          placeholder={field.placeholder}
          className="w-full px-2 py-1 rounded-lg text-[12px]"
          style={{ border: '1px solid var(--border)', background: 'white' }} />
      </div>
    );
  }
  return null;
}

function ShellIcon({ shell }) {
  const [src, setSrc] = useState(`/icons/${shell.icon}`);
  return (
    <Image src={src} alt="" width={40} height={40}
      onError={() => setSrc(`/icons/${shell.icon_fallback || 'gamepad.png'}`)} />
  );
}
