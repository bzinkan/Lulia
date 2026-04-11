'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Loader2, ChevronDown, ChevronRight, Check, SkipForward, Plus } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';

export default function CurriculumPage() {
  const { activeClassId, classes } = useClassContext();
  const activeClass = classes.find(c => c.class_id === activeClassId);

  const [coverage, setCoverage] = useState(null);
  const [position, setPosition] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedUnit, setExpandedUnit] = useState(null);

  // Generate form state
  const [showGenerate, setShowGenerate] = useState(false);
  const [genState, setGenState] = useState('');
  const [genScope, setGenScope] = useState('full_year');
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (activeClassId) loadData();
  }, [activeClassId]);

  async function loadData() {
    setLoading(true);
    try {
      const [gapsData, posData] = await Promise.all([
        apiFetch(`/api/v1/classes/${activeClassId}/intelligence/curriculum/gaps`),
        apiFetch(`/api/v1/classes/${activeClassId}/intelligence/curriculum/position`),
      ]);
      setCoverage(gapsData);
      setPosition(posData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    if (!genState || !activeClass) return;
    setGenerating(true);
    try {
      await apiFetch(`/api/v1/classes/${activeClassId}/intelligence/curriculum/generate`, {
        method: 'POST',
        body: JSON.stringify({
          grade_level: activeClass.grade_level || '4',
          subject: activeClass.subject || 'Math',
          state_code: genState,
          scope: genScope,
        }),
      });
      setShowGenerate(false);
      loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(false);
    }
  }

  async function handleJump(calendarId) {
    try {
      await apiFetch(`/api/v1/classes/${activeClassId}/intelligence/curriculum/jump`, {
        method: 'POST',
        body: JSON.stringify({ target_calendar_id: calendarId }),
      });
      loadData();
    } catch (e) {
      console.error(e);
    }
  }

  if (!activeClassId) {
    return (
      <div className="max-w-[900px] mx-auto text-center py-16">
        <Image src="/icons/calendar.png" alt="" width={48} height={48} className="mx-auto mb-4" style={{ opacity: 0.5 }} />
        <h2 className="font-serif text-[22px] mb-2" style={{ color: 'var(--text-dark)' }}>
          Select a class to view curriculum
        </h2>
        <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
          Choose a class from the tabs above to manage its curriculum
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--coral)' }} />
      </div>
    );
  }

  const hasCurriculum = coverage?.has_curriculum;

  return (
    <div className="max-w-[900px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-[26px]" style={{ color: 'var(--text-dark)' }}>
            Curriculum
          </h1>
          <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
            {activeClass?.name || 'Class'} — {activeClass?.subject || ''} {activeClass?.grade_level || ''}
          </p>
        </div>
        {hasCurriculum && (
          <div className="text-right">
            <div className="text-[28px] font-serif font-bold" style={{ color: 'var(--coral)' }}>
              {coverage.year_progress_pct}%
            </div>
            <div className="text-[11px] font-semibold" style={{ color: 'var(--text-light)' }}>
              {coverage.total_covered} / {coverage.total_standards} standards
            </div>
          </div>
        )}
      </div>

      {/* No curriculum — show setup options */}
      {!hasCurriculum && (
        <div
          className="rounded-card p-8 text-center"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
        >
          <Image src="/icons/calendar.png" alt="" width={56} height={56} className="mx-auto mb-4" />
          <h2 className="font-serif text-[22px] mb-2" style={{ color: 'var(--text-dark)' }}>
            Set Up Your Curriculum
          </h2>
          <p className="text-[14px] mb-6 max-w-md mx-auto" style={{ color: 'var(--text-mid)' }}>
            Upload your school&apos;s pacing guide, or let Lulia generate one from your state standards.
            You can always edit, rearrange, and adjust later.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/library"
              className="px-6 py-3 rounded-xl font-semibold text-[14px] text-white"
              style={{ background: 'var(--sage)' }}
            >
              Upload Pacing Guide
            </Link>
            <button
              onClick={() => setShowGenerate(true)}
              className="px-6 py-3 rounded-xl font-semibold text-[14px] text-white"
              style={{ background: 'var(--coral)' }}
            >
              Generate From State Standards
            </button>
          </div>

          {/* Silent coverage stats (if any) */}
          {coverage?.total_covered > 0 && (
            <div className="mt-6 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
              <p className="text-[12px] font-semibold" style={{ color: 'var(--text-light)' }}>
                Even without a curriculum, we&apos;ve tracked your standards usage:
              </p>
              <p className="text-[14px] font-bold mt-1" style={{ color: 'var(--sage)' }}>
                {coverage.total_covered} standards covered so far this year
              </p>
            </div>
          )}
        </div>
      )}

      {/* Generate curriculum modal */}
      {showGenerate && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={() => setShowGenerate(false)}
        >
          <div
            className="rounded-card p-6 w-full max-w-md mx-4"
            style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
            onClick={e => e.stopPropagation()}
          >
            <h3 className="font-serif text-[20px] mb-4" style={{ color: 'var(--text-dark)' }}>
              Generate Curriculum
            </h3>

            <label className="block text-[12px] font-semibold mb-1" style={{ color: 'var(--text-mid)' }}>
              State
            </label>
            <select
              value={genState}
              onChange={e => setGenState(e.target.value)}
              className="w-full rounded-xl px-3 py-2 text-[14px] mb-4"
              style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
            >
              <option value="">Select your state...</option>
              {['AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <label className="block text-[12px] font-semibold mb-1" style={{ color: 'var(--text-mid)' }}>
              Scope
            </label>
            <div className="flex gap-3 mb-6">
              {[
                { id: 'full_year', label: 'Full Year', desc: 'Complete scope & sequence' },
                { id: 'next_unit', label: 'One Unit', desc: 'Just the first unit to start' },
              ].map(opt => (
                <button
                  key={opt.id}
                  onClick={() => setGenScope(opt.id)}
                  className="flex-1 p-3 rounded-xl text-left"
                  style={{
                    border: genScope === opt.id ? '2px solid var(--coral)' : '1px solid var(--border)',
                    background: genScope === opt.id ? 'var(--cream)' : 'white',
                  }}
                >
                  <div className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>{opt.label}</div>
                  <div className="text-[11px]" style={{ color: 'var(--text-light)' }}>{opt.desc}</div>
                </button>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleGenerate}
                disabled={!genState || generating}
                className="flex-1 py-2.5 rounded-xl font-semibold text-[14px] text-white disabled:opacity-50"
                style={{ background: 'var(--coral)' }}
              >
                {generating ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" /> Generating...
                  </span>
                ) : 'Generate'}
              </button>
              <button
                onClick={() => setShowGenerate(false)}
                className="px-4 py-2.5 rounded-xl font-semibold text-[14px]"
                style={{ color: 'var(--text-mid)', border: '1px solid var(--border)' }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Curriculum units list */}
      {hasCurriculum && coverage.units && (
        <div className="space-y-3">
          {coverage.units.map((unit, i) => {
            const isExpanded = expandedUnit === unit.calendar_id;
            const isCurrent = position?.has_curriculum &&
              position?.current_unit === unit.unit_name;
            const isComplete = unit.pct === 100;

            return (
              <div
                key={unit.calendar_id}
                className="rounded-card overflow-hidden"
                style={{
                  background: 'var(--warm-card)',
                  border: isCurrent
                    ? '2px solid var(--coral)'
                    : '1px solid var(--border)',
                  boxShadow: isCurrent ? '0 4px 16px rgba(216,108,82,0.15)' : '0 2px 8px var(--shadow)',
                }}
              >
                {/* Unit header */}
                <button
                  onClick={() => setExpandedUnit(isExpanded ? null : unit.calendar_id)}
                  className="w-full flex items-center gap-3 p-4 text-left"
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
                >
                  {/* Status icon */}
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{
                      background: isComplete ? 'var(--green-bg, #DCFCE7)' : isCurrent ? 'rgba(216,108,82,0.12)' : 'var(--cream)',
                    }}
                  >
                    {isComplete ? (
                      <Check className="w-4 h-4" style={{ color: 'var(--green-text, #16A34A)' }} />
                    ) : (
                      <span className="text-[12px] font-bold" style={{ color: isCurrent ? 'var(--coral)' : 'var(--text-light)' }}>
                        {unit.unit_number}
                      </span>
                    )}
                  </div>

                  {/* Unit info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-bold truncate" style={{ color: 'var(--text-dark)' }}>
                        {unit.unit_name}
                      </span>
                      {isCurrent && (
                        <span
                          className="text-[9px] font-bold px-2 py-0.5 rounded-full"
                          style={{ background: 'rgba(216,108,82,0.12)', color: 'var(--coral)' }}
                        >
                          CURRENT
                        </span>
                      )}
                      {unit.unit_status === 'skipped' && (
                        <span
                          className="text-[9px] font-bold px-2 py-0.5 rounded-full"
                          style={{ background: 'var(--amber-bg, #FEF3C7)', color: 'var(--amber, #D97706)' }}
                        >
                          SKIPPED
                        </span>
                      )}
                    </div>
                    {unit.topic && (
                      <div className="text-[12px] truncate" style={{ color: 'var(--text-light)' }}>
                        {unit.topic}
                      </div>
                    )}
                  </div>

                  {/* Progress */}
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <div className="text-right">
                      <div className="text-[13px] font-bold" style={{
                        color: isComplete ? 'var(--green-text, #16A34A)' : 'var(--text-dark)'
                      }}>
                        {unit.standards_covered}/{unit.standards_total}
                      </div>
                    </div>
                    <div className="w-[60px] h-2 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${unit.pct}%`,
                          background: isComplete ? 'var(--green-text, #16A34A)' : 'var(--coral)',
                        }}
                      />
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4" style={{ color: 'var(--text-light)' }} />
                    ) : (
                      <ChevronRight className="w-4 h-4" style={{ color: 'var(--text-light)' }} />
                    )}
                  </div>
                </button>

                {/* Expanded: individual standards */}
                {isExpanded && (
                  <div className="px-4 pb-4" style={{ borderTop: '1px solid var(--border)' }}>
                    <div className="space-y-2 mt-3">
                      {unit.standards_list?.map(std => (
                        <div key={std.code} className="flex items-center gap-2 py-1">
                          <div
                            className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                            style={{
                              background: std.covered ? 'var(--green-bg, #DCFCE7)' : 'var(--cream)',
                              border: std.covered ? 'none' : '1px solid var(--border)',
                            }}
                          >
                            {std.covered && (
                              <Check className="w-3 h-3" style={{ color: 'var(--green-text, #16A34A)' }} />
                            )}
                          </div>
                          <span
                            className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded"
                            style={{
                              background: std.covered ? 'var(--green-bg, #DCFCE7)' : 'var(--cream)',
                              color: std.covered ? 'var(--green-text, #16A34A)' : 'var(--text-mid)',
                            }}
                          >
                            {std.code}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Unit actions */}
                    {!isCurrent && !isComplete && (
                      <div className="flex gap-2 mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                        <button
                          onClick={() => handleJump(unit.calendar_id)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold"
                          style={{ background: 'var(--cream)', color: 'var(--coral)', border: '1px solid var(--border)' }}
                        >
                          <SkipForward className="w-3.5 h-3.5" /> Jump to this unit
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Add unit / generate next */}
          <div className="flex gap-3 mt-4">
            <button
              onClick={() => setShowGenerate(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-semibold"
              style={{ background: 'var(--cream)', color: 'var(--coral)', border: '1px solid var(--border)' }}
            >
              <Plus className="w-4 h-4" /> Add / Generate Unit
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
