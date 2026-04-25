'use client';
import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
import {
  ChevronLeft, ChevronRight, Clock, CheckCircle, Loader2,
  RotateCcw, Sparkles, Upload, X, Pencil, Trash2, Plus,
} from 'lucide-react';
import { apiFetch, apiUpload } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';
import CurriculumPickerModal from '@/components/CurriculumPickerModal';
import StandardsPickerModal from '@/components/StandardsPickerModal';
import RefineDayModal from '@/components/RefineDayModal';

const DURATIONS = [
  { id: 'day', label: '1 Day' },
  { id: 'week', label: 'Full Week' },
  { id: 'custom', label: 'Custom Days' },
];

const DAYS = [
  { id: 'mon', label: 'Mon' },
  { id: 'tue', label: 'Tue' },
  { id: 'wed', label: 'Wed' },
  { id: 'thu', label: 'Thu' },
  { id: 'fri', label: 'Fri' },
];

const MATERIAL_TYPES = [
  { id: 'worksheet', label: 'Worksheet', icon: 'document.png' },
  { id: 'interactive', label: 'Interactive Activity', icon: 'interactive.png' },
  { id: 'quiz_test', label: 'Assessment / Quiz', icon: 'check.png' },
  { id: 'slides', label: 'Google Slides', icon: 'clipboard.png' },
  { id: 'video', label: 'Video', icon: 'video-camera.png' },
  { id: 'forms', label: 'Google Forms Quiz', icon: 'report.png' },
];

const CONTENT_SOURCE_OPTIONS = [
  { id: 'curriculum', label: 'From My Curriculum', desc: 'Use your current unit and standards' },
  { id: 'standards', label: 'Specific Standards', desc: 'Pick standards to focus on' },
  { id: 'custom', label: 'Custom Prompt', desc: 'Describe what you want to teach' },
];

function getMonday(d) {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(date.setDate(diff));
}

function formatDate(d) {
  return d.toISOString().split('T')[0];
}

export default function PlannerPage() {
  const { activeClassId, classes, teacherId } = useClassContext();
  const activeClass = classes.find(c => c.class_id === activeClassId);

  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));
  const [duration, setDuration] = useState('week');
  const [selectedDays, setSelectedDays] = useState(['mon', 'tue', 'wed', 'thu', 'fri']);

  // Pre-planning configuration
  const [selectedMaterials, setSelectedMaterials] = useState(['worksheet']);
  const [contentSource, setContentSource] = useState('curriculum');
  const [customPrompt, setCustomPrompt] = useState('');
  const [standardsInput, setStandardsInput] = useState('');

  // Picker modals
  const [showCurriculumPicker, setShowCurriculumPicker] = useState(false);
  const [showStandardsPicker, setShowStandardsPicker] = useState(false);
  const [selectedUnit, setSelectedUnit] = useState(null); // { calendar_id, unit_name, standards: [] }
  const [selectedStandards, setSelectedStandards] = useState([]); // [{ code, description? }]

  // Plan state
  const [plan, setPlan] = useState(null);
  const [suggesting, setSuggesting] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approved, setApproved] = useState(null);
  const [error, setError] = useState(null);
  const [syncToClassroom, setSyncToClassroom] = useState(false);
  const [editingDay, setEditingDay] = useState(null);
  const calUploadRef = useRef(null);

  const hasClassroom = activeClass?.google_classroom_course_id;

  function shiftWeek(dir) {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + dir * 7);
    setWeekStart(d);
    setPlan(null);
    setApproved(null);
  }

  function toggleDay(day) {
    setSelectedDays(prev =>
      prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]
    );
  }

  function toggleMaterial(id) {
    setSelectedMaterials(prev =>
      prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
    );
  }

  async function handleSuggest() {
    if (selectedMaterials.length === 0) {
      setError('Select at least one material type to generate.');
      return;
    }
    setSuggesting(true);
    setError(null);
    setPlan(null);
    setApproved(null);
    try {
      const data = await apiFetch('/api/v1/plans/suggest', {
        method: 'POST',
        body: JSON.stringify({
          class_id: activeClassId,
          teacher_id: teacherId,
          duration_type: duration === 'custom' ? 'week' : duration,
          selected_days: duration === 'day' ? [selectedDays[0] || 'mon'] : selectedDays,
          week_start_date: formatDate(weekStart),
          // Teacher preferences
          material_types: selectedMaterials,
          content_source: contentSource,
          custom_prompt: contentSource === 'custom' ? customPrompt : null,
          standards_input: contentSource === 'standards'
            ? selectedStandards.join(', ')
            : contentSource === 'curriculum' && selectedUnit
              ? selectedUnit.standards?.join(', ')
              : null,
        }),
      });
      setPlan(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setSuggesting(false);
    }
  }

  const [generationProgress, setGenerationProgress] = useState(null);

  async function handleApprove() {
    if (!plan?.plan_id) return;
    setApproving(true);
    setError(null);
    setGenerationProgress(null);
    try {
      // Kick off background generation
      await apiFetch(`/api/v1/plans/${plan.plan_id}/approve`, {
        method: 'PUT',
        body: JSON.stringify({ sync_to_classroom: syncToClassroom }),
      });
      // Poll for progress
      pollProgress(plan.plan_id);
    } catch (e) {
      setError(e.message);
      setApproving(false);
    }
  }

  async function pollProgress(planId) {
    const maxPolls = 120; // 6 minutes max (120 x 3s)
    for (let i = 0; i < maxPolls; i++) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const data = await apiFetch(`/api/v1/plans/${planId}`);
        const progress = data?.plan_data?.generation_progress;
        if (progress) {
          setGenerationProgress(progress);
        }
        if (data.status === 'complete') {
          setApproved({
            plan_id: planId,
            status: 'complete',
            assignments: progress?.assignments || [],
            total_generated: progress?.assignments?.filter(a => a.status === 'complete').length || 0,
          });
          setApproving(false);
          return;
        }
        if (data.status === 'failed') {
          setError('Plan generation failed. Some materials may have been partially generated.');
          setApproving(false);
          return;
        }
      } catch (e) {
        // Poll error — keep trying
      }
    }
    setError('Generation timed out. Check the Assignments page for any completed materials.');
    setApproving(false);
  }

  async function handleStartOver() {
    if (!plan?.plan_id) return;
    await apiFetch(`/api/v1/plans/${plan.plan_id}/start-over`, { method: 'PUT' }).catch(() => {});
    setPlan(null);
    setApproved(null);
    handleSuggest();
  }

  async function handleSaveEdit(dayIndex, updatedDay) {
    if (!plan?.plan_id) return;
    const updatedPlans = [...(plan.daily_plans || [])];
    updatedPlans[dayIndex] = updatedDay;
    try {
      await apiFetch(`/api/v1/plans/${plan.plan_id}/modify`, {
        method: 'PUT',
        body: JSON.stringify({ daily_plans: updatedPlans }),
      });
      setPlan({ ...plan, daily_plans: updatedPlans });
      setEditingDay(null);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleCalendarUpload(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('teacher_id', teacherId);
    try {
      const result = await apiUpload('/api/v1/upload/school-calendar', formData);
      alert(`School calendar uploaded: ${result.stored} non-school days extracted.`);
    } catch (e) {
      setError(e.message);
    }
  }

  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekEnd.getDate() + 4);

  return (
    <div className="max-w-[1000px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-[26px]" style={{ color: 'var(--text-dark)' }}>
            Weekly Planner
          </h1>
          <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
            Plan your week — AI generates everything
          </p>
        </div>
      </div>

      {/* Week Navigator + Duration */}
      <div
        className="rounded-card p-4 mb-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
      >
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <button onClick={() => shiftWeek(-1)} className="p-1.5 rounded-lg" style={{ color: 'var(--text-mid)' }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--cream)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <Image src="/icons/calendar.png" alt="" width={20} height={20} style={{ opacity: 0.7 }} />
              <span className="text-[14px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                {weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} — {weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            </div>
            <button onClick={() => shiftWeek(1)} className="p-1.5 rounded-lg" style={{ color: 'var(--text-mid)' }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--cream)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
          <div className="flex gap-2">
            {DURATIONS.map(d => (
              <button key={d.id} onClick={() => setDuration(d.id)}
                className="px-3 py-1.5 rounded-xl text-[13px] font-semibold transition-colors"
                style={duration === d.id
                  ? { background: 'var(--coral)', color: 'white' }
                  : { background: 'var(--cream)', color: 'var(--text-mid)', border: '1px solid var(--border)' }
                }>
                {d.label}
              </button>
            ))}
          </div>
        </div>

        {duration === 'custom' && (
          <div className="flex gap-2 mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
            {DAYS.map(d => (
              <button key={d.id} onClick={() => toggleDay(d.id)}
                className="px-4 py-1.5 rounded-xl text-[13px] font-semibold transition-colors"
                style={selectedDays.includes(d.id)
                  ? { background: 'rgba(216,108,82,0.12)', color: 'var(--coral)', border: '1px solid var(--coral-light, #E8927A)' }
                  : { background: 'var(--cream)', color: 'var(--text-light)', border: '1px solid var(--border)' }
                }>
                {d.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── PRE-PLANNING CONFIGURATION ── */}
      {!plan && !suggesting && !approved && (
        <>
          {/* Material Types */}
          <div
            className="rounded-card p-5 mb-5"
            style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
          >
            <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
              What materials do you need?
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {MATERIAL_TYPES.map(mt => {
                const isSelected = selectedMaterials.includes(mt.id);
                return (
                  <button
                    key={mt.id}
                    onClick={() => toggleMaterial(mt.id)}
                    className="flex items-center gap-3 p-3 rounded-xl text-left transition-all"
                    style={{
                      background: isSelected ? 'rgba(216,108,82,0.08)' : 'var(--cream)',
                      border: isSelected ? '2px solid var(--coral)' : '1px solid var(--border)',
                    }}
                  >
                    <Image src={`/icons/${mt.icon}`} alt="" width={28} height={28}
                      style={{ opacity: isSelected ? 1 : 0.5 }} />
                    <span className="text-[13px] font-semibold"
                      style={{ color: isSelected ? 'var(--coral)' : 'var(--text-mid)' }}>
                      {mt.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Content Source */}
          <div
            className="rounded-card p-5 mb-5"
            style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
          >
            <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
              What should I teach?
            </h2>
            <div className="space-y-2 mb-4">
              {CONTENT_SOURCE_OPTIONS.map(opt => (
                <button
                  key={opt.id}
                  onClick={() => {
                    setContentSource(opt.id);
                    if (opt.id === 'curriculum') setShowCurriculumPicker(true);
                    else if (opt.id === 'standards') setShowStandardsPicker(true);
                  }}
                  className="w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all"
                  style={{
                    background: contentSource === opt.id ? 'rgba(107,160,138,0.08)' : 'var(--cream)',
                    border: contentSource === opt.id ? '2px solid var(--sage)' : '1px solid var(--border)',
                  }}
                >
                  <div
                    className="w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0"
                    style={{ borderColor: contentSource === opt.id ? 'var(--sage)' : 'var(--border)' }}
                  >
                    {contentSource === opt.id && (
                      <div className="w-2 h-2 rounded-full" style={{ background: 'var(--sage)' }} />
                    )}
                  </div>
                  <div>
                    <div className="text-[14px] font-bold" style={{ color: 'var(--text-dark)' }}>
                      {opt.label}
                    </div>
                    <div className="text-[12px]" style={{ color: 'var(--text-light)' }}>
                      {opt.desc}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Curriculum unit selection */}
            {contentSource === 'curriculum' && selectedUnit && (
              <div className="p-3 rounded-xl" style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>
                      Unit {selectedUnit.unit_name}
                    </span>
                    {selectedUnit.topic && (
                      <span className="text-[12px] ml-2" style={{ color: 'var(--text-light)' }}>
                        — {selectedUnit.topic}
                      </span>
                    )}
                  </div>
                  <button onClick={() => setShowCurriculumPicker(true)}
                    className="text-[12px] font-semibold" style={{ color: 'var(--coral)', background: 'none', border: 'none', cursor: 'pointer' }}>
                    Change
                  </button>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {selectedUnit.standards?.slice(0, 6).map(s => (
                    <span key={s} className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold"
                      style={{ background: 'rgba(216,108,82,0.1)', color: 'var(--coral)' }}>
                      {s}
                    </span>
                  ))}
                  {(selectedUnit.standards?.length || 0) > 6 && (
                    <span className="text-[9px]" style={{ color: 'var(--text-light)' }}>
                      +{selectedUnit.standards.length - 6} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Standards selection */}
            {contentSource === 'standards' && selectedStandards.length > 0 && (
              <div className="p-3 rounded-xl" style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>
                    {selectedStandards.length} standard{selectedStandards.length !== 1 ? 's' : ''} selected
                  </span>
                  <button onClick={() => setShowStandardsPicker(true)}
                    className="text-[12px] font-semibold" style={{ color: 'var(--coral)', background: 'none', border: 'none', cursor: 'pointer' }}>
                    Change
                  </button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {selectedStandards.slice(0, 8).map(code => (
                    <span key={code} className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold"
                      style={{ background: 'rgba(107,160,138,0.12)', color: 'var(--sage)' }}>
                      {code}
                    </span>
                  ))}
                  {selectedStandards.length > 8 && (
                    <span className="text-[9px]" style={{ color: 'var(--text-light)' }}>
                      +{selectedStandards.length - 8} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Custom prompt */}
            {contentSource === 'custom' && (
              <div>
                <label className="block text-[12px] font-semibold mb-1" style={{ color: 'var(--text-mid)' }}>
                  What do you want to teach this week?
                </label>
                <textarea
                  value={customPrompt}
                  onChange={e => setCustomPrompt(e.target.value)}
                  placeholder="e.g., Introduction to fractions using visual models. Students should understand equivalent fractions and be able to compare fractions with unlike denominators."
                  rows={3}
                  className="w-full rounded-xl px-3 py-2 text-[14px] resize-none"
                  style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
                />
              </div>
            )}
          </div>

          {/* Suggest button */}
          <button
            onClick={handleSuggest}
            disabled={selectedMaterials.length === 0}
            className="w-full py-3.5 rounded-xl font-semibold text-[15px] text-white transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, var(--coral), var(--coral-light, #E8927A))' }}
          >
            <Sparkles className="w-4 h-4" />
            Suggest Plan
          </button>
        </>
      )}

      {/* Loading */}
      {suggesting && (
        <div
          className="rounded-card p-12 text-center"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
        >
          <div
            className="w-8 h-8 border-2 rounded-full animate-spin mx-auto mb-4"
            style={{ borderColor: 'var(--coral)', borderTopColor: 'transparent' }}
          />
          <p className="text-[14px] font-semibold" style={{ color: 'var(--text-mid)' }}>Planning your week...</p>
          <p className="text-[12px] mt-1" style={{ color: 'var(--text-light)' }}>
            The AI is reading your calendar, standards, and history
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-card p-4 mb-4 mt-4" style={{ background: 'var(--red-bg, #FEF2F2)', border: '1px solid #EF4444' }}>
          <p className="text-[13px]" style={{ color: '#EF4444' }}>{error}</p>
        </div>
      )}

      {/* Plan Preview */}
      {plan && !approved && (
        <div className="mt-5">
          {/* Rationale */}
          <div
            className="rounded-card p-4 mb-4"
            style={{ background: 'rgba(107,160,138,0.08)', borderLeft: '3px solid var(--sage)' }}
          >
            <p className="text-[13px]" style={{ color: 'var(--text-dark)' }}>{plan.rationale}</p>
          </div>

          {/* Day tiles — each opens RefineDayModal */}
          <div className="mb-4">
            <p className="text-[12px] font-semibold mb-2" style={{ color: 'var(--text-mid)' }}>
              Refine each day — confirm materials before generating
            </p>
            <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.max((plan.daily_plans || []).length, 1)}, minmax(0,1fr))` }}>
              {(plan.daily_plans || []).map((dp, i) => {
                const wos = dp.work_orders || [];
                const confirmedCount = wos.filter(w => w.confirmed).length;
                const done = wos.length > 0 && confirmedCount === wos.length;
                return (
                  <button key={i} onClick={() => setEditingDay(i)}
                    className="p-3 rounded-xl text-left transition-all"
                    style={{
                      background: done ? 'rgba(107,160,138,0.08)' : 'var(--cream)',
                      border: `2px solid ${done ? 'var(--sage)' : 'var(--border)'}`,
                      cursor: 'pointer',
                    }}>
                    <div className="text-[10px] font-bold uppercase mb-1" style={{ color: done ? 'var(--sage)' : 'var(--coral)' }}>
                      {dp.day}
                    </div>
                    <div className="text-[12px] font-bold line-clamp-2 mb-2" style={{ color: 'var(--text-dark)' }}>
                      {dp.title}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px]" style={{ color: 'var(--text-light)' }}>
                        {wos.length} material{wos.length !== 1 ? 's' : ''}
                      </span>
                      <span className="text-[10px] font-bold"
                        style={{ color: done ? 'var(--sage)' : '#F59E0B' }}>
                        {done ? '✓ Ready' : `⚠ ${confirmedCount}/${wos.length}`}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Rationale fold below tiles — keep visible */}
          <div className="space-y-3 mb-6">
            {(plan.daily_plans || []).map((dp, i) => (
              <DayCard key={i} day={dp} onEdit={() => setEditingDay(i)} />
            ))}
          </div>

          {/* Action buttons */}
          <div className="flex flex-col gap-3">
            {hasClassroom && (
              <label
                className="flex items-center gap-2 px-4 py-2 rounded-xl cursor-pointer"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}
              >
                <input type="checkbox" checked={syncToClassroom}
                  onChange={e => setSyncToClassroom(e.target.checked)}
                  style={{ accentColor: 'var(--coral)' }} />
                <span className="text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                  Also post to Google Classroom
                </span>
              </label>
            )}
            {/* Progress indicator during generation */}
            {approving && generationProgress && (
              <div
                className="rounded-card p-4 mb-3"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                    Generating materials...
                  </span>
                  <span className="text-[13px] font-bold" style={{ color: 'var(--coral)' }}>
                    {generationProgress.completed} / {generationProgress.total}
                  </span>
                </div>
                <div className="h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${(generationProgress.completed / Math.max(generationProgress.total, 1)) * 100}%`,
                      background: 'var(--sage)',
                    }}
                  />
                </div>
                {generationProgress.assignments?.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {generationProgress.assignments.map((a, i) => (
                      <div key={i} className="flex items-center gap-2 text-[12px]">
                        <CheckCircle className="w-3.5 h-3.5" style={{ color: a.status === 'complete' ? 'var(--green-text, #16A34A)' : '#EF4444' }} />
                        <span style={{ color: 'var(--text-mid)' }}>
                          {a.day?.toUpperCase()} — {a.title || a.template}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                          style={{ background: 'var(--cream)', color: 'var(--text-light)' }}>
                          {a.template}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {(() => {
              const allConfirmed = (plan.daily_plans || []).every(d => (d.work_orders || []).every(w => w.confirmed));
              const pendingCount = (plan.daily_plans || []).reduce((sum, d) => sum + (d.work_orders || []).filter(w => !w.confirmed).length, 0);
              return (
            <div className="flex gap-3">
              <button onClick={handleApprove} disabled={approving || !allConfirmed}
                className="flex-1 py-3 rounded-xl font-semibold text-[14px] text-white flex items-center justify-center gap-2 disabled:opacity-50"
                style={{ background: allConfirmed ? 'var(--sage)' : 'var(--text-light)' }}
                title={!allConfirmed ? `${pendingCount} work order${pendingCount !== 1 ? 's' : ''} still need confirmation` : ''}>
                {approving ? <><Loader2 className="w-4 h-4 animate-spin" /> {generationProgress ? `${generationProgress.completed}/${generationProgress.total} done...` : 'Starting...'}</>
                  : allConfirmed
                    ? <><CheckCircle className="w-4 h-4" /> Accept &amp; Generate</>
                    : <>Confirm all {pendingCount > 0 ? `(${pendingCount} remaining)` : ''}</>}
              </button>
              <button onClick={handleStartOver}
                className="px-4 py-3 rounded-xl font-semibold text-[14px] flex items-center gap-2"
                style={{ color: 'var(--text-mid)', background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
                <RotateCcw className="w-4 h-4" /> Start Over
              </button>
            </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* Approved results */}
      {approved && (
        <div className="mt-5">
          <div className="rounded-card p-4 mb-4"
            style={{ background: 'var(--green-bg, #DCFCE7)', border: '1px solid var(--green-text, #16A34A)' }}>
            <div className="flex items-center gap-2" style={{ color: 'var(--green-text, #16A34A)' }}>
              <CheckCircle className="w-5 h-5" />
              <span className="font-bold text-[14px]">
                Plan approved — {approved.total_generated} materials generated
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {(approved.assignments || []).map((a, i) => (
              <div key={i} className="rounded-card p-3 flex items-center justify-between"
                style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-bold uppercase" style={{ color: 'var(--coral)', width: 32 }}>
                    {a.day}
                  </span>
                  <span className="text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                    {a.title || a.template}
                  </span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--cream)', color: 'var(--text-light)' }}>
                    {a.template}
                  </span>
                </div>
                <span className="text-[12px] font-bold"
                  style={{ color: a.status === 'complete' ? 'var(--green-text, #16A34A)' : '#EF4444' }}>
                  {a.status}
                </span>
              </div>
            ))}
          </div>
          {/* Generate another plan button */}
          <button
            onClick={() => { setPlan(null); setApproved(null); }}
            className="mt-4 w-full py-3 rounded-xl font-semibold text-[14px] flex items-center justify-center gap-2"
            style={{ color: 'var(--coral)', background: 'var(--cream)', border: '1px solid var(--border)' }}
          >
            <Plus className="w-4 h-4" /> Plan Another Week
          </button>
        </div>
      )}

      {/* Curriculum Picker Modal */}
      {showCurriculumPicker && (
        <CurriculumPickerModal
          classId={activeClassId}
          onSelect={(unit) => {
            setSelectedUnit(unit);
            setStandardsInput(unit.standards?.join(', ') || '');
            setShowCurriculumPicker(false);
          }}
          onClose={() => setShowCurriculumPicker(false)}
        />
      )}

      {/* Standards Picker Modal */}
      {showStandardsPicker && (
        <StandardsPickerModal
          subject={activeClass?.subject || ''}
          gradeLevel={activeClass?.grade_level || ''}
          stateCode={activeClass?.state_code || ''}
          initialSelected={selectedStandards}
          onConfirm={(codes) => {
            setSelectedStandards(codes);
            setStandardsInput(codes.join(', '));
            setShowStandardsPicker(false);
          }}
          onClose={() => setShowStandardsPicker(false)}
        />
      )}

      {/* Refine Day Modal */}
      {editingDay !== null && plan?.daily_plans?.[editingDay] && (
        <RefineDayModal
          day={plan.daily_plans[editingDay]}
          subject={activeClass?.subject || ''}
          classDefaultAccommodations={activeClass?.default_accommodations || []}
          onSave={(updated) => handleSaveEdit(editingDay, updated)}
          onClose={() => setEditingDay(null)}
        />
      )}
    </div>
  );
}


function DayCard({ day, onEdit }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-card overflow-hidden"
      style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
      <button onClick={() => setExpanded(!expanded)}
        className="w-full text-left p-4 flex items-center justify-between transition-colors"
        style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--cream)'}
        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-bold uppercase w-8" style={{ color: 'var(--coral)' }}>
            {day.day}
          </span>
          <span className="text-[14px] font-bold" style={{ color: 'var(--text-dark)' }}>
            {day.title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {(day.standards || []).slice(0, 3).map(s => (
            <span key={s} className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold"
              style={{ background: 'var(--cream)', color: 'var(--coral)', border: '1px solid rgba(216,108,82,0.2)' }}>
              {s}
            </span>
          ))}
          <span className="text-[11px]" style={{ color: 'var(--text-light)' }}>
            {day.procedures?.length || 0} phases
          </span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="mt-3 space-y-2">
            {(day.procedures || []).map((proc, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="flex items-center gap-1 min-w-[100px]">
                  <Clock className="w-3 h-3" style={{ color: 'var(--text-light)' }} />
                  <span className="text-[11px]" style={{ color: 'var(--text-light)' }}>{proc.duration_minutes}m</span>
                  <span className="text-[11px] font-bold" style={{ color: 'var(--text-mid)' }}>{proc.phase}</span>
                </div>
                <span className="text-[12px] flex-1" style={{ color: 'var(--text-mid)' }}>
                  {proc.description}
                </span>
              </div>
            ))}
          </div>

          {day.work_orders?.length > 0 && (
            <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
              <p className="text-[11px] mb-1" style={{ color: 'var(--text-light)' }}>Materials to generate:</p>
              <div className="flex gap-2 flex-wrap">
                {day.work_orders.map((wo, i) => (
                  <span key={i} className="text-[11px] px-2 py-1 rounded-lg font-semibold"
                    style={{ background: 'var(--cream)', color: 'var(--coral)', border: '1px solid rgba(216,108,82,0.2)' }}>
                    {wo.output_template_id} ({wo.question_count}q)
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
            <button onClick={(e) => { e.stopPropagation(); onEdit(); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold"
              style={{ background: 'var(--cream)', color: 'var(--coral)', border: '1px solid var(--border)' }}>
              <Pencil className="w-3.5 h-3.5" /> Edit this day
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


function EditDayModal({ day, onSave, onClose }) {
  const [title, setTitle] = useState(day.title || '');
  const [procedures, setProcedures] = useState(day.procedures || []);

  function updateProc(i, field, value) {
    const updated = [...procedures];
    updated[i] = { ...updated[i], [field]: value };
    setProcedures(updated);
  }

  function removeProc(i) { setProcedures(procedures.filter((_, idx) => idx !== i)); }

  function addProc() {
    setProcedures([...procedures, { phase: 'New Phase', duration_minutes: 10, description: '', standards_addressed: [] }]);
  }

  function handleSave() {
    onSave({ ...day, title, procedures });
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="rounded-card p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
            Edit {day.day?.toUpperCase()}
          </h3>
          <button onClick={onClose} style={{ color: 'var(--text-light)' }}><X className="w-5 h-5" /></button>
        </div>

        <label className="block text-[12px] font-semibold mb-1" style={{ color: 'var(--text-mid)' }}>Lesson Title</label>
        <input type="text" value={title} onChange={e => setTitle(e.target.value)}
          className="w-full rounded-xl px-3 py-2 text-[14px] mb-4"
          style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }} />

        <label className="block text-[12px] font-semibold mb-2" style={{ color: 'var(--text-mid)' }}>Procedure Phases</label>
        <div className="space-y-2 mb-3">
          {procedures.map((proc, i) => (
            <div key={i} className="flex items-start gap-2 p-2 rounded-xl"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
              <div className="flex-1 space-y-1">
                <input type="text" value={proc.phase} onChange={e => updateProc(i, 'phase', e.target.value)}
                  className="w-full text-[12px] font-bold px-2 py-1 rounded-lg"
                  style={{ border: '1px solid var(--border)', color: 'var(--text-dark)' }} placeholder="Phase name" />
                <div className="flex gap-2">
                  <input type="number" value={proc.duration_minutes}
                    onChange={e => updateProc(i, 'duration_minutes', parseInt(e.target.value) || 0)}
                    className="w-16 text-[12px] px-2 py-1 rounded-lg"
                    style={{ border: '1px solid var(--border)', color: 'var(--text-dark)' }} placeholder="min" />
                  <input type="text" value={proc.description}
                    onChange={e => updateProc(i, 'description', e.target.value)}
                    className="flex-1 text-[12px] px-2 py-1 rounded-lg"
                    style={{ border: '1px solid var(--border)', color: 'var(--text-dark)' }} placeholder="Description" />
                </div>
              </div>
              <button onClick={() => removeProc(i)} style={{ color: 'var(--text-light)' }}>
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
        <button onClick={addProc} className="flex items-center gap-1 text-[12px] font-semibold mb-4"
          style={{ color: 'var(--coral)', background: 'none', border: 'none', cursor: 'pointer' }}>
          <Plus className="w-3.5 h-3.5" /> Add phase
        </button>

        <div className="flex gap-3">
          <button onClick={handleSave}
            className="flex-1 py-2.5 rounded-xl font-semibold text-[14px] text-white"
            style={{ background: 'var(--coral)' }}>
            Save Changes
          </button>
          <button onClick={onClose}
            className="px-4 py-2.5 rounded-xl font-semibold text-[14px]"
            style={{ color: 'var(--text-mid)', border: '1px solid var(--border)' }}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
