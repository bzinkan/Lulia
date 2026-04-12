'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ChevronLeft, ChevronRight, Upload, Info } from 'lucide-react';
import { apiFetch, apiUpload } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';
import DayDetailModal from '@/components/DayDetailModal';
import SchoolCalendarPreviewModal from '@/components/SchoolCalendarPreviewModal';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DAY_TYPE_LABELS = {
  school_day: null,
  no_school: 'No school',
  holiday: 'Holiday',
  half_day: 'Half day',
  professional_development: 'PD',
  snow_day: 'Snow day',
  break: 'Break',
};
const DAY_TYPE_COLORS = {
  no_school: '#94A3B8',
  holiday: '#EF4444',
  half_day: '#E9B44C',
  professional_development: '#8B5CF6',
  snow_day: '#3B82F6',
  break: '#F97316',
};

function firstOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function isoDate(d) {
  const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export default function CalendarPage() {
  const { activeClassId, classes, teacherId } = useClassContext();
  const activeClass = classes.find(c => c.class_id === activeClassId);

  const [monthStart, setMonthStart] = useState(() => firstOfMonth(new Date()));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [inboxCount, setInboxCount] = useState(0);
  const [selectedDate, setSelectedDate] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [parsedCalendar, setParsedCalendar] = useState(null);
  const calUploadRef = useRef(null);

  async function handleCalendarUpload(file) {
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      // Phase 1: parse only — modal handles review + save
      const parsed = await apiUpload('/api/v1/upload/school-calendar/parse', formData);
      setParsedCalendar(parsed);
    } catch (e) {
      alert(`Parse failed: ${e.message}`);
    } finally {
      setUploading(false);
    }
  }

  async function handleCalendarSaved() {
    // Refetch the month so the new overlay shows immediately
    if (activeClassId) {
      const refreshed = await apiFetch(`/api/v1/manager/classes/${activeClassId}/calendar?month=${monthParam}&teacher_id=${teacherId}`);
      setData(refreshed);
    }
  }

  const monthLabel = monthStart.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  const monthParam = `${monthStart.getFullYear()}-${String(monthStart.getMonth() + 1).padStart(2, '0')}`;
  const today = new Date();

  useEffect(() => {
    apiFetch('/api/v1/manager/grading-inbox/count')
      .then(d => setInboxCount(d.count || 0))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!activeClassId) return;
    setLoading(true);
    apiFetch(`/api/v1/manager/classes/${activeClassId}/calendar?month=${monthParam}&teacher_id=${teacherId}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeClassId, monthParam, teacherId]);

  // Build the 6x7 grid: pad with days from prev/next month so every cell is filled
  const cells = useMemo(() => {
    const firstDayOfWeek = monthStart.getDay(); // Sun = 0
    const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate();
    const out = [];
    // Pad start
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
      const d = new Date(monthStart); d.setDate(-i);
      out.push({ date: d, inMonth: false });
    }
    // Month days
    for (let i = 1; i <= daysInMonth; i++) {
      const d = new Date(monthStart.getFullYear(), monthStart.getMonth(), i);
      out.push({ date: d, inMonth: true });
    }
    // Pad end to fill 6 rows
    while (out.length < 42) {
      const last = out[out.length - 1].date;
      const d = new Date(last); d.setDate(last.getDate() + 1);
      out.push({ date: d, inMonth: false });
    }
    return out;
  }, [monthStart]);

  function shiftMonth(dir) {
    const d = new Date(monthStart);
    d.setMonth(d.getMonth() + dir);
    setMonthStart(firstOfMonth(d));
  }

  function openDay(dateObj) {
    setSelectedDate(isoDate(dateObj));
  }

  function onSchoolSaved(updated) {
    // Patch the local data cache so the grid reflects the new status immediately
    if (!data) return;
    setData({
      ...data,
      days: {
        ...data.days,
        [updated.date]: {
          assignments: data.days[updated.date]?.assignments || [],
          school: {
            day_type: updated.day_type,
            label: updated.label,
            notes: updated.notes,
            is_school_day: updated.is_school_day,
          },
        },
      },
    });
  }

  const selectedDay = selectedDate && data?.days?.[selectedDate];

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div
            className="w-11 h-11 rounded-[12px] flex items-center justify-center"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}
          >
            <Image src="/icons/calendar.png" alt="" width={32} height={32} />
          </div>
          <div>
            <h1 className="font-serif text-[26px] leading-tight" style={{ color: 'var(--text-dark)' }}>
              Calendar
            </h1>
            <p className="text-[13px]" style={{ color: 'var(--text-mid)' }}>
              {activeClass ? `${activeClass.name} · ${monthLabel}` : monthLabel}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative group">
            <button
              type="button"
              className="w-6 h-6 rounded-full flex items-center justify-center"
              style={{ background: 'var(--cream)', color: 'var(--text-mid)', border: '1px solid var(--border)', cursor: 'help' }}
              aria-label="What does uploading do?"
            >
              <Info className="w-3.5 h-3.5" />
            </button>
            <div
              className="absolute right-0 top-full mt-2 w-72 p-3 rounded-xl text-[12px] z-20 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
              style={{ background: 'var(--text-dark)', color: 'white', boxShadow: '0 6px 20px rgba(0,0,0,0.2)', lineHeight: 1.45 }}
            >
              <strong className="block mb-1" style={{ color: 'var(--mustard, #E9B44C)' }}>What uploading does</strong>
              Upload your district or school's yearly calendar (PDF, DOCX, CSV, or TXT).
              Lulia reads it and extracts <strong>no-school days</strong> — holidays, PD days, breaks,
              half days — then marks them on your Calendar.
              <br /><br />
              The <strong>Planner</strong> also uses this data: it skips non-school days when generating
              a weekly plan, so assignments never land on a day off.
              <br /><br />
              You can also click any day on the Calendar to mark it a no-school day yourself.
            </div>
          </div>
          <input
            type="file"
            ref={calUploadRef}
            accept=".pdf,.docx,.csv,.txt"
            className="hidden"
            onChange={e => { if (e.target.files[0]) handleCalendarUpload(e.target.files[0]); e.target.value = ''; }}
          />
          <button
            onClick={() => calUploadRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-semibold disabled:opacity-50"
            style={{ background: 'var(--cream)', color: 'var(--coral)', border: '1px solid var(--border)' }}
          >
            <Upload className="w-3.5 h-3.5" /> {uploading ? 'Uploading…' : 'Upload School Calendar'}
          </button>
        </div>
      </div>

      {/* Month nav */}
      <div className="rounded-card p-3 mb-4 flex items-center gap-2"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <button onClick={() => shiftMonth(-1)} className="p-1.5 rounded-lg"
          style={{ color: 'var(--text-mid)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-[15px] font-semibold min-w-[140px] text-center" style={{ color: 'var(--text-dark)' }}>
          {monthLabel}
        </span>
        <button onClick={() => shiftMonth(1)} className="p-1.5 rounded-lg"
          style={{ color: 'var(--text-mid)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
          <ChevronRight className="w-4 h-4" />
        </button>
        <button onClick={() => setMonthStart(firstOfMonth(new Date()))}
          className="ml-2 px-2.5 py-1 rounded-lg text-[11px] font-semibold"
          style={{ color: 'var(--coral)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
          Today
        </button>
      </div>

      {/* Weekday header row */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {WEEKDAYS.map(w => (
          <div key={w} className="text-center text-[10px] uppercase tracking-wider font-bold py-1"
            style={{ color: 'var(--text-light)' }}>
            {w}
          </div>
        ))}
      </div>

      {/* Month grid */}
      <div className="grid grid-cols-7 gap-1 rounded-card p-2"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        {cells.map((cell, i) => {
          const key = isoDate(cell.date);
          const dayData = data?.days?.[key] || { assignments: [], school: null };
          const isToday = isSameDay(cell.date, today);
          const isNonSchool = dayData.school && !dayData.school.is_school_day;
          const hasNote = !!dayData.school?.notes;
          const typeLabel = dayData.school ? DAY_TYPE_LABELS[dayData.school.day_type] : null;
          const typeColor = dayData.school ? DAY_TYPE_COLORS[dayData.school.day_type] : null;

          return (
            <button key={i} onClick={() => openDay(cell.date)}
              className="relative min-h-[92px] p-2 text-left rounded-lg transition-colors"
              style={{
                background: isNonSchool
                  ? 'repeating-linear-gradient(45deg, var(--cream), var(--cream) 6px, #F2E8D9 6px, #F2E8D9 12px)'
                  : cell.inMonth ? 'var(--warm-card)' : '#FAF5EC',
                border: isToday ? '2px solid var(--coral)' : '1px solid var(--border)',
                opacity: cell.inMonth ? 1 : 0.55,
                cursor: 'pointer',
              }}>
              {/* Date number */}
              <div className="flex items-start justify-between mb-1">
                <span className="text-[12px] font-bold"
                  style={{ color: isToday ? 'var(--coral)' : cell.inMonth ? 'var(--text-dark)' : 'var(--text-light)' }}>
                  {cell.date.getDate()}
                </span>
                <div className="flex items-center gap-1">
                  {hasNote && (
                    <Image src="/icons/postit.png" alt="note" width={32} height={32}
                      style={{ marginTop: -6, marginRight: -4 }} />
                  )}
                  {typeLabel && (
                    <span className="text-[8px] font-bold uppercase tracking-wide px-1 py-0.5 rounded"
                      style={{ background: 'white', color: typeColor, border: `1px solid ${typeColor}` }}>
                      {typeLabel}
                    </span>
                  )}
                </div>
              </div>

              {/* Assignment chips */}
              <div className="space-y-0.5">
                {dayData.assignments.slice(0, 2).map(a => (
                  <div key={a.assignment_id}
                    className="text-[10px] px-1.5 py-0.5 rounded font-semibold truncate"
                    style={{
                      background: 'rgba(216,108,82,0.1)',
                      color: 'var(--coral)',
                      opacity: isNonSchool ? 0.5 : 1,
                    }}>
                    {(a.title || a.output_template_id || '').slice(0, 18)}
                  </div>
                ))}
                {dayData.assignments.length > 2 && (
                  <div className="text-[10px]" style={{ color: 'var(--text-light)' }}>
                    +{dayData.assignments.length - 2} more
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {loading && (
        <p className="text-center mt-3 text-[12px]" style={{ color: 'var(--text-light)' }}>Loading…</p>
      )}

      {selectedDate && (
        <DayDetailModal
          date={selectedDate}
          assignments={selectedDay?.assignments || []}
          school={selectedDay?.school || null}
          teacherId={teacherId}
          onSaved={onSchoolSaved}
          onClose={() => setSelectedDate(null)}
        />
      )}

      {parsedCalendar && (
        <SchoolCalendarPreviewModal
          parsed={parsedCalendar}
          teacherId={teacherId}
          onSaved={handleCalendarSaved}
          onClose={() => setParsedCalendar(null)}
        />
      )}
    </div>
  );
}
