'use client';
import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { X, CheckCircle, ExternalLink, Loader2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const DAY_TYPES = [
  { id: 'school_day',                label: 'School day',    color: 'var(--sage)' },
  { id: 'no_school',                 label: 'No school',     color: '#94A3B8' },
  { id: 'half_day',                  label: 'Half day',      color: '#E9B44C' },
  { id: 'holiday',                   label: 'Holiday',       color: '#EF4444' },
  { id: 'professional_development',  label: 'PD day',        color: '#8B5CF6' },
  { id: 'snow_day',                  label: 'Snow day',      color: '#3B82F6' },
  { id: 'break',                     label: 'Break',         color: '#F97316' },
];

/**
 * DayDetailModal — click a day cell to open this.
 * Shows assignments for the day + editable school status + sticky note.
 *
 * Props:
 *   date: "YYYY-MM-DD"
 *   assignments: [{ assignment_id, title, output_template_id, status, submissions }]
 *   school: { day_type, label, notes } | null
 *   teacherId: string (for save)
 *   onSaved: (updatedSchool) => void
 *   onClose: () => void
 */
export default function DayDetailModal({ date, assignments = [], school, teacherId, onSaved, onClose }) {
  const [dayType, setDayType] = useState(school?.day_type || 'school_day');
  const [label, setLabel] = useState(school?.label || '');
  const [notes, setNotes] = useState(school?.notes || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const dateObj = new Date(date + 'T00:00:00');
  const nicelyFormatted = dateObj.toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  });

  async function handleSave() {
    setSaving(true); setError(null);
    try {
      const data = await apiFetch(`/api/v1/manager/school-calendar/${date}`, {
        method: 'PUT',
        body: JSON.stringify({
          teacher_id: teacherId,
          day_type: dayType,
          label: label || null,
          notes: notes || null,
        }),
      });
      onSaved?.(data);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
          <div>
            <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
              {nicelyFormatted}
            </h3>
            <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-light)' }}>
              {assignments.length} assignment{assignments.length !== 1 ? 's' : ''}
              {school?.notes ? ' · has note' : ''}
            </p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-light)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Assignments */}
          <div>
            <h4 className="text-[12px] font-bold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
              Assignments
            </h4>
            {assignments.length === 0 ? (
              <p className="text-[13px] italic" style={{ color: 'var(--text-light)' }}>
                Nothing scheduled this day.
              </p>
            ) : (
              <div className="space-y-2">
                {assignments.map(a => (
                  <Link key={a.assignment_id} href={`/assignments/${a.assignment_id}`}
                    className="flex items-center justify-between p-3 rounded-xl transition-colors"
                    style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-semibold truncate" style={{ color: 'var(--text-dark)' }}>
                          {a.title || a.output_template_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold"
                          style={{ background: 'var(--warm-card)', color: 'var(--text-mid)', border: '1px solid var(--border)' }}>
                          {a.output_template_id}
                        </span>
                        {a.submissions > 0 && (
                          <span className="text-[10px] font-semibold" style={{ color: 'var(--coral)' }}>
                            {a.submissions} sub
                          </span>
                        )}
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-light)' }} />
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* School status */}
          <div>
            <h4 className="text-[12px] font-bold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
              School Status
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {DAY_TYPES.map(t => {
                const active = dayType === t.id;
                return (
                  <button key={t.id} onClick={() => setDayType(t.id)}
                    className="flex items-center gap-2 p-2 rounded-lg text-left"
                    style={{
                      background: active ? 'var(--cream)' : 'transparent',
                      border: `1px solid ${active ? t.color : 'var(--border)'}`,
                      cursor: 'pointer',
                    }}>
                    <span className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: t.color }} />
                    <span className="text-[12px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                      {t.label}
                    </span>
                  </button>
                );
              })}
            </div>
            {dayType !== 'school_day' && (
              <input
                value={label}
                onChange={e => setLabel(e.target.value)}
                placeholder="Optional label (e.g. Spring Break, Easter Monday)"
                className="mt-2 w-full px-3 py-2 rounded-xl text-[12px]"
                style={{ border: '1px solid var(--border)', background: 'white' }} />
            )}
          </div>

          {/* Sticky note */}
          <div>
            <h4 className="text-[12px] font-bold mb-2 uppercase tracking-wider flex items-center gap-1.5"
              style={{ color: 'var(--text-light)' }}>
              <Image src="/icons/postit.png" alt="" width={16} height={16} /> Note
            </h4>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value.slice(0, 200))}
              rows={4}
              placeholder="Jot a reminder to yourself..."
              className="w-full px-3 py-2 rounded-xl text-[13px] resize-none"
              style={{
                background: notes ? '#FFF5C4' : 'white',
                border: `1px solid ${notes ? '#E9B44C' : 'var(--border)'}`,
                color: 'var(--text-dark)',
                fontFamily: notes ? "'Caveat', cursive, sans-serif" : 'inherit',
                fontSize: notes ? '15px' : '13px',
                lineHeight: notes ? '1.4' : '1.3',
              }} />
            <p className="text-[10px] mt-1 text-right" style={{ color: 'var(--text-light)' }}>
              {notes.length}/200
            </p>
          </div>

          {error && (
            <div className="p-2.5 rounded-lg text-[12px]"
              style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444', color: '#EF4444' }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-5 flex justify-end gap-2" style={{ borderTop: '1px solid var(--border)' }}>
          <button onClick={onClose}
            className="px-4 py-2 rounded-xl text-[13px] font-semibold"
            style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
            Cancel
          </button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white flex items-center gap-2 disabled:opacity-50"
            style={{ background: 'var(--sage)' }}>
            {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving…</> : <><CheckCircle className="w-4 h-4" /> Save</>}
          </button>
        </div>
      </div>
    </div>
  );
}
