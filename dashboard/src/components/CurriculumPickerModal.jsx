'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { X, Check, Loader2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';

/**
 * Modal that shows the teacher's curriculum units.
 * Teacher clicks a unit → returns its calendar_id + standard codes.
 *
 * Props:
 *   classId: string — active class ID
 *   onSelect: (unit) => void — called with { calendar_id, unit_name, standards: string[] }
 *   onClose: () => void
 */
export default function CurriculumPickerModal({ classId, onSelect, onClose }) {
  const [loading, setLoading] = useState(true);
  const [coverage, setCoverage] = useState(null);

  useEffect(() => {
    if (!classId) return;
    setLoading(true);
    apiFetch(`/api/v1/classes/${classId}/intelligence/curriculum/gaps`)
      .then(data => setCoverage(data))
      .catch(() => setCoverage(null))
      .finally(() => setLoading(false));
  }, [classId]);

  function handleSelect(unit) {
    const codes = (unit.standards_list || []).map(s => s.code).filter(Boolean);
    onSelect({
      calendar_id: unit.calendar_id,
      unit_name: unit.unit_name,
      topic: unit.topic,
      standards: codes,
    });
  }

  const hasCurriculum = coverage?.has_curriculum;
  const units = coverage?.units || [];

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-lg mx-4 max-h-[80vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5" style={{ borderBottom: '1px solid var(--border)' }}>
          <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
            Select a Unit
          </h3>
          <button onClick={onClose} style={{ color: 'var(--text-light)' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--coral)' }} />
            </div>
          )}

          {!loading && !hasCurriculum && (
            <div className="text-center py-8">
              <Image src="/icons/calendar.png" alt="" width={48} height={48} className="mx-auto mb-3" style={{ opacity: 0.5 }} />
              <h4 className="font-serif text-[18px] mb-2" style={{ color: 'var(--text-dark)' }}>
                No Curriculum Set Up
              </h4>
              <p className="text-[13px] mb-4" style={{ color: 'var(--text-mid)' }}>
                Upload a pacing guide or generate a curriculum first.
              </p>
              <Link
                href="/curriculum"
                className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white"
                style={{ background: 'var(--coral)' }}
                onClick={onClose}
              >
                Set Up Curriculum
              </Link>
            </div>
          )}

          {!loading && hasCurriculum && units.length > 0 && (
            <div className="space-y-2">
              {units.map(unit => {
                const isCurrent = unit.unit_status === 'in_progress';
                const isComplete = unit.pct === 100;

                return (
                  <button
                    key={unit.calendar_id}
                    onClick={() => handleSelect(unit)}
                    className="w-full text-left p-4 rounded-xl transition-all"
                    style={{
                      background: isCurrent ? 'rgba(216,108,82,0.06)' : 'var(--cream)',
                      border: isCurrent ? '2px solid var(--coral)' : '1px solid var(--border)',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={e => { if (!isCurrent) e.currentTarget.style.borderColor = 'var(--sage)'; }}
                    onMouseLeave={e => { if (!isCurrent) e.currentTarget.style.borderColor = 'var(--border)'; }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[12px] font-bold" style={{
                          color: isComplete ? 'var(--green-text, #16A34A)' : 'var(--text-light)'
                        }}>
                          Unit {unit.unit_number}
                        </span>
                        <span className="text-[14px] font-bold" style={{ color: 'var(--text-dark)' }}>
                          {unit.unit_name}
                        </span>
                        {isCurrent && (
                          <span className="text-[9px] font-bold px-2 py-0.5 rounded-full"
                            style={{ background: 'rgba(216,108,82,0.12)', color: 'var(--coral)' }}>
                            CURRENT
                          </span>
                        )}
                        {isComplete && (
                          <Check className="w-4 h-4" style={{ color: 'var(--green-text, #16A34A)' }} />
                        )}
                      </div>
                      <span className="text-[12px] font-semibold" style={{
                        color: isComplete ? 'var(--green-text, #16A34A)' : 'var(--text-mid)'
                      }}>
                        {unit.standards_covered}/{unit.standards_total}
                      </span>
                    </div>

                    {unit.topic && (
                      <p className="text-[12px] mb-2" style={{ color: 'var(--text-light)' }}>
                        {unit.topic}
                      </p>
                    )}

                    {/* Progress bar */}
                    <div className="h-1.5 rounded-full overflow-hidden mb-2" style={{ background: 'var(--border)' }}>
                      <div className="h-full rounded-full" style={{
                        width: `${unit.pct}%`,
                        background: isComplete ? 'var(--green-text, #16A34A)' : 'var(--coral)',
                      }} />
                    </div>

                    {/* Standards tags */}
                    <div className="flex flex-wrap gap-1">
                      {(unit.standards_list || []).slice(0, 8).map(s => (
                        <span key={s.code} className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold"
                          style={{
                            background: s.covered ? 'var(--green-bg, #DCFCE7)' : 'var(--cream)',
                            color: s.covered ? 'var(--green-text, #16A34A)' : 'var(--text-light)',
                            border: `1px solid ${s.covered ? 'rgba(22,163,74,0.2)' : 'var(--border)'}`,
                          }}>
                          {s.code}
                        </span>
                      ))}
                      {(unit.standards_list || []).length > 8 && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full"
                          style={{ color: 'var(--text-light)' }}>
                          +{unit.standards_list.length - 8} more
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
