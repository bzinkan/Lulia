'use client';
import { useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import { X, Play, Loader2, FileText, Bookmark, Sparkles, Info, Wand2, BookOpen } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { BASE_SETTINGS } from '@/lib/gameShellConfigs';
import StandardsPickerModal from '@/components/StandardsPickerModal';
import CurriculumPickerModal from '@/components/CurriculumPickerModal';
import { useClassContext } from '@/components/ClassContext';

const SOURCE_TABS = [
  { id: 'assignment', label: 'From Assignment', desc: 'Reuse a worksheet you already made', icon: FileText, baseCost: 0 },
  { id: 'curriculum', label: 'From Curriculum', desc: 'Pick a unit from your curriculum — questions align with its topic + standards', icon: BookOpen, baseCost: 0 },
  { id: 'standards',  label: 'From Standards',  desc: 'Pull questions from assignments tagged to these standards (or generate fresh if none match)', icon: Bookmark, baseCost: 0 },
  { id: 'custom',     label: 'Describe Topic',  desc: 'Generate fresh questions from a prompt', icon: Sparkles, baseCost: 2 },
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
  const [selectedUnit, setSelectedUnit] = useState(null); // { calendar_id, unit_name, topic, standards }
  const [showCurriculumPicker, setShowCurriculumPicker] = useState(false);

  // Standards-match-count probe → tells us if Standards mode will fall through to Haiku
  const [standardsMatchCount, setStandardsMatchCount] = useState(null);
  const [checkingStandards, setCheckingStandards] = useState(false);

  // Settings
  const baseSettingsFiltered = useMemo(() => {
    // If question_count is locked for this shell, drop it from BASE_SETTINGS
    if (shell.question_count_locked) return BASE_SETTINGS.filter(f => f.key !== 'question_count');
    return BASE_SETTINGS;
  }, [shell]);
  const allSettings = useMemo(() => [...baseSettingsFiltered, ...(shell.extra_settings || [])], [baseSettingsFiltered, shell]);

  const initial = useMemo(() => {
    const acc = {};
    BASE_SETTINGS.forEach(f => { acc[f.key] = f.default; });
    (shell.extra_settings || []).forEach(f => { acc[f.key] = f.default; });
    if (shell.question_count_default) acc.question_count = shell.question_count_default;
    return acc;
  }, [shell]);
  const [settings, setSettings] = useState(initial);

  const [suggestingCategories, setSuggestingCategories] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState(null);

  // Load teacher's assignments
  useEffect(() => {
    apiFetch(`/api/v1/assignments?teacher_id=${teacherId}&limit=50`)
      .then(d => setAssignments(d.assignments || d.items || d || []))
      .catch(() => setAssignments([]));
  }, [teacherId]);

  // Keep Bingo's question_count synced with board_size
  useEffect(() => {
    if (shell.question_count_derived_from === 'board_size') {
      const bs = settings.board_size || 5;
      if (settings.question_count !== bs * bs) {
        setSettings(s => ({ ...s, question_count: bs * bs }));
      }
    }
  }, [settings.board_size, shell.question_count_derived_from]);

  // Check standards match count whenever standards change
  useEffect(() => {
    if (source !== 'standards' || standards.length === 0) {
      setStandardsMatchCount(null);
      return;
    }
    let cancelled = false;
    setCheckingStandards(true);
    apiFetch(`/api/v1/games/standards-match-count?teacher_id=${teacherId}&standards=${encodeURIComponent(standards.join(','))}`)
      .then(d => { if (!cancelled) setStandardsMatchCount(d.match_count); })
      .catch(() => { if (!cancelled) setStandardsMatchCount(null); })
      .finally(() => { if (!cancelled) setCheckingStandards(false); });
    return () => { cancelled = true; };
  }, [source, standards, teacherId]);

  async function handleSuggestCategories() {
    setSuggestingCategories(true);
    setError(null);
    try {
      const body = {
        source_type: source,
        teacher_id: teacherId,
        assignment_id: source === 'assignment' ? assignmentId : null,
        standards: source === 'standards' ? standards : null,
        prompt: source === 'custom' ? prompt : null,
      };
      const data = await apiFetch('/api/v1/games/suggest-categories', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (data.categories && data.categories.length > 0) {
        setSettings(s => ({ ...s, categories: data.categories.join(', ') }));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSuggestingCategories(false);
    }
  }

  async function handleLaunch() {
    setError(null);

    let questionSource;
    if (source === 'assignment') {
      if (!assignmentId) { setError('Pick an assignment first.'); return; }
      questionSource = { type: 'assignment', assignment_id: assignmentId };
    } else if (source === 'curriculum') {
      if (!selectedUnit) { setError('Pick a curriculum unit first.'); return; }
      questionSource = {
        type: 'curriculum',
        calendar_id: selectedUnit.calendar_id,
        unit_name: selectedUnit.unit_name,
        topic: selectedUnit.topic,
        standards: selectedUnit.standards || [],
        question_count: settings.question_count,
      };
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
      if (result.error) setError(result.error);
      else onLaunched?.(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLaunching(false);
    }
  }

  const selectedTab = SOURCE_TABS.find(t => t.id === source);

  // Compute effective cost for the footer pill
  const effectiveCost = useMemo(() => {
    if (source === 'custom') return 2;
    if (source === 'standards' && standards.length > 0 && standardsMatchCount === 0) return 2;
    return 0;
  }, [source, standards, standardsMatchCount]);

  const willGenerateViaAI = source === 'custom'
    || (source === 'standards' && standards.length > 0 && standardsMatchCount === 0);

  const showCategorySuggest = !!shell.needs_categories
    && (
      (source === 'assignment' && assignmentId) ||
      (source === 'standards' && standards.length > 0) ||
      (source === 'custom' && prompt.trim().length >= 10)
    );

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
                      {t.baseCost === 0 ? 'Free*' : `${t.baseCost} credits`}
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

          {source === 'curriculum' && (
            <div>
              <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
                Pick a curriculum unit
              </label>
              {selectedUnit ? (
                <div className="mb-2 p-3 rounded-xl" style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>
                        {selectedUnit.unit_name}
                      </div>
                      {selectedUnit.topic && (
                        <div className="text-[11px]" style={{ color: 'var(--text-mid)' }}>
                          {selectedUnit.topic}
                        </div>
                      )}
                      {selectedUnit.standards?.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {selectedUnit.standards.slice(0, 5).map(s => (
                            <span key={s} className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold"
                              style={{ background: 'rgba(216,108,82,0.1)', color: 'var(--coral)' }}>
                              {s}
                            </span>
                          ))}
                          {selectedUnit.standards.length > 5 && (
                            <span className="text-[9px]" style={{ color: 'var(--text-light)' }}>
                              +{selectedUnit.standards.length - 5} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <button onClick={() => setShowCurriculumPicker(true)}
                      className="text-[11px] font-semibold px-2 py-1 rounded-lg"
                      style={{ color: 'var(--coral)', background: 'transparent', border: '1px solid var(--coral)', cursor: 'pointer' }}>
                      Change
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-[11px] italic mb-2" style={{ color: 'var(--text-light)' }}>None selected yet.</p>
              )}
              {!selectedUnit && (
                <button onClick={() => setShowCurriculumPicker(true)}
                  className="text-[12px] font-semibold px-3 py-1.5 rounded-lg"
                  style={{ color: 'var(--coral)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                  Pick a unit
                </button>
              )}
              <div className="mt-2 p-2.5 rounded-lg flex items-start gap-2 text-[11px]"
                style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)', color: 'var(--text-mid)' }}>
                <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#3B82F6' }} />
                <span>
                  We first check your assignments for questions tagged to this unit&apos;s standards (free).
                  If none match, Lulia generates fresh questions from the unit topic for <strong>2 credits</strong>.
                </span>
              </div>
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
                <p className="text-[11px] italic mb-2" style={{ color: 'var(--text-light)' }}>None selected yet.</p>
              )}
              <button onClick={() => setShowStandardsPicker(true)}
                className="text-[12px] font-semibold px-3 py-1.5 rounded-lg"
                style={{ color: 'var(--coral)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                {standards.length === 0 ? 'Pick standards' : 'Change standards'}
              </button>

              {/* Live indicator of what will happen */}
              {standards.length > 0 && (
                <div className="mt-2 p-2.5 rounded-lg flex items-start gap-2 text-[11px]"
                  style={willGenerateViaAI
                    ? { background: 'rgba(216,108,82,0.06)', border: '1px solid rgba(216,108,82,0.25)', color: 'var(--text-mid)' }
                    : { background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)', color: 'var(--text-mid)' }}>
                  <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5"
                    style={{ color: willGenerateViaAI ? 'var(--coral)' : '#3B82F6' }} />
                  <span>
                    {checkingStandards
                      ? 'Checking your assignments for matches…'
                      : willGenerateViaAI
                        ? <>No existing questions cover these standards. <strong>Lulia will generate fresh questions for 2 credits.</strong></>
                        : <>Found <strong>{standardsMatchCount} matching question{standardsMatchCount === 1 ? '' : 's'}</strong> in your assignments — free to play.</>
                    }
                  </span>
                </div>
              )}
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
            {shell.question_count_locked && (
              <div className="mb-2 p-2 rounded-lg text-[11px]"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--text-mid)' }}>
                <strong>{shell.name}</strong> uses <strong>{settings.question_count} questions</strong>
                {shell.question_count_derived_from ? ` (set by ${shell.question_count_derived_from.replace('_', ' ')})` : ''}.
              </div>
            )}
            <div className="space-y-2.5">
              {allSettings.map(f => (
                <SettingField key={f.key} field={f} value={settings[f.key]}
                  onChange={v => setSettings({ ...settings, [f.key]: v })}
                  onSuggest={f.suggestable && showCategorySuggest ? handleSuggestCategories : null}
                  suggesting={suggestingCategories && f.suggestable} />
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
            style={effectiveCost > 0
              ? { background: 'rgba(216,108,82,0.12)', color: 'var(--coral)' }
              : { background: 'rgba(107,160,138,0.12)', color: 'var(--sage)' }}>
            {effectiveCost > 0 ? `${effectiveCost} credits` : 'Free'}
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
              {launching ? <><Loader2 className="w-4 h-4 animate-spin" /> Launching…</> : <><Play className="w-4 h-4" /> Launch Game</>}
            </button>
          </div>
        </div>

        {showCurriculumPicker && (
          <CurriculumPickerModal
            classId={classId}
            onSelect={(unit) => { setSelectedUnit(unit); setShowCurriculumPicker(false); }}
            onClose={() => setShowCurriculumPicker(false)}
          />
        )}
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

function SettingField({ field, value, onChange, onSuggest, suggesting }) {
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
        <div className="flex items-center justify-between mb-1">
          <label className="text-[12px] font-semibold" style={{ color: 'var(--text-dark)' }}>{field.label}</label>
          {onSuggest && (
            <button onClick={onSuggest} disabled={suggesting}
              className="text-[11px] font-semibold flex items-center gap-1 px-2 py-0.5 rounded-lg"
              style={{ color: 'var(--sage)', background: 'rgba(107,160,138,0.08)', border: '1px solid var(--sage)', cursor: 'pointer' }}>
              {suggesting
                ? <><Loader2 className="w-3 h-3 animate-spin" /> Thinking…</>
                : <><Wand2 className="w-3 h-3" /> Suggest</>}
            </button>
          )}
        </div>
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
