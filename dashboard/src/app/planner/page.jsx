'use client';
import { useState } from 'react';
import { Calendar, ChevronLeft, ChevronRight, Clock, CheckCircle, Loader2, RotateCcw, Pencil, Sparkles } from 'lucide-react';
import { apiFetch } from '@/lib/api';

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
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));
  const [duration, setDuration] = useState('week');
  const [selectedDays, setSelectedDays] = useState(['mon', 'tue', 'wed', 'thu', 'fri']);
  const [plan, setPlan] = useState(null);
  const [suggesting, setSuggesting] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approved, setApproved] = useState(null);
  const [error, setError] = useState(null);

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

  async function handleSuggest() {
    setSuggesting(true);
    setError(null);
    setPlan(null);
    setApproved(null);
    try {
      const data = await apiFetch('/api/v1/plans/suggest', {
        method: 'POST',
        body: JSON.stringify({
          class_id: '00000000-0000-0000-0000-000000000010',
          teacher_id: '00000000-0000-0000-0000-000000000001',
          duration_type: duration === 'custom' ? 'week' : duration,
          selected_days: duration === 'day' ? [selectedDays[0] || 'mon'] : selectedDays,
          week_start_date: formatDate(weekStart),
        }),
      });
      setPlan(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setSuggesting(false);
    }
  }

  async function handleApprove() {
    if (!plan?.plan_id) return;
    setApproving(true);
    setError(null);
    try {
      const data = await apiFetch(`/api/v1/plans/${plan.plan_id}/approve`, {
        method: 'PUT',
      });
      setApproved(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setApproving(false);
    }
  }

  async function handleStartOver() {
    if (!plan?.plan_id) return;
    await apiFetch(`/api/v1/plans/${plan.plan_id}/start-over`, { method: 'PUT' }).catch(() => {});
    setPlan(null);
    setApproved(null);
    handleSuggest();
  }

  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekEnd.getDate() + 4);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Weekly Planner</h1>
          <p className="text-sm text-gray-500 mt-1">Plan your week — AI generates everything</p>
        </div>
      </div>

      {/* Week Navigator + Duration */}
      <div className="bg-white rounded-[14px] p-4 mb-6" style={{ border: '1px solid #E7E5E4' }}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          {/* Week navigator */}
          <div className="flex items-center gap-3">
            <button onClick={() => shiftWeek(-1)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-orange-500" />
              <span className="text-sm font-medium text-gray-800">
                {weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} — {weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            </div>
            <button onClick={() => shiftWeek(1)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          {/* Duration selector */}
          <div className="flex gap-2">
            {DURATIONS.map(d => (
              <button
                key={d.id}
                onClick={() => setDuration(d.id)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  duration === d.id
                    ? 'bg-orange-500 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>

        {/* Custom day selector */}
        {duration === 'custom' && (
          <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
            {DAYS.map(d => (
              <button
                key={d.id}
                onClick={() => toggleDay(d.id)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  selectedDays.includes(d.id)
                    ? 'bg-orange-100 text-orange-700 border border-orange-300'
                    : 'bg-gray-50 text-gray-400 border border-gray-200'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        )}

        {/* Suggest button */}
        {!plan && !suggesting && (
          <div className="mt-4 pt-3 border-t border-gray-100">
            <button
              onClick={handleSuggest}
              className="w-full bg-orange-500 hover:bg-orange-600 text-white px-4 py-3 rounded-xl font-medium text-sm transition-colors flex items-center justify-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              Suggest Plan
            </button>
          </div>
        )}
      </div>

      {/* Loading */}
      {suggesting && (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <div className="w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-gray-600">Planning your week...</p>
          <p className="text-xs text-gray-400 mt-1">The AI is reading your calendar, standards, and history</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-[14px] p-4 mb-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Plan Preview */}
      {plan && !approved && (
        <div>
          {/* Rationale */}
          <div className="bg-orange-50 rounded-[14px] p-4 mb-4" style={{ borderLeft: '3px solid #F97316' }}>
            <p className="text-sm text-orange-800">{plan.rationale}</p>
          </div>

          {/* Day cards */}
          <div className="space-y-3 mb-6">
            {(plan.daily_plans || []).map((dp, i) => (
              <DayCard key={i} day={dp} />
            ))}
          </div>

          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleApprove}
              disabled={approving}
              className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white px-4 py-3 rounded-xl font-medium text-sm transition-colors flex items-center justify-center gap-2"
            >
              {approving ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Generating materials...</>
              ) : (
                <><CheckCircle className="w-4 h-4" /> Accept &amp; Generate</>
              )}
            </button>
            <button
              onClick={handleStartOver}
              className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 px-4 py-3 rounded-xl font-medium text-sm transition-colors flex items-center gap-2"
            >
              <RotateCcw className="w-4 h-4" /> Start Over
            </button>
          </div>
        </div>
      )}

      {/* Approved results */}
      {approved && (
        <div>
          <div className="bg-green-50 border border-green-200 rounded-[14px] p-4 mb-4">
            <div className="flex items-center gap-2 text-green-700">
              <CheckCircle className="w-5 h-5" />
              <span className="font-medium">Plan approved — {approved.total_generated} materials generated</span>
            </div>
          </div>
          <div className="space-y-2">
            {(approved.assignments || []).map((a, i) => (
              <div key={i} className="bg-white rounded-[14px] p-3 flex items-center justify-between" style={{ border: '1px solid #E7E5E4' }}>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium uppercase text-orange-500">{a.day}</span>
                  <span className="text-sm text-gray-800">{a.title || a.template}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-500">{a.template}</span>
                </div>
                <span className={`text-xs font-medium ${a.status === 'complete' ? 'text-green-600' : 'text-red-600'}`}>
                  {a.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function DayCard({ day }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left p-4 flex items-center justify-between hover:bg-gray-50/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold uppercase text-orange-500 w-8">{day.day}</span>
          <span className="text-sm font-medium text-gray-800">{day.title}</span>
        </div>
        <div className="flex items-center gap-2">
          {(day.standards || []).slice(0, 3).map(s => (
            <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-orange-50 text-orange-700 border border-orange-200">
              {s}
            </span>
          ))}
          <span className="text-xs text-gray-400">{day.procedures?.length || 0} phases</span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100">
          {/* Procedures */}
          <div className="mt-3 space-y-2">
            {(day.procedures || []).map((proc, i) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <div className="flex items-center gap-1 min-w-[100px]">
                  <Clock className="w-3 h-3 text-gray-400" />
                  <span className="text-xs text-gray-400">{proc.duration_minutes}m</span>
                  <span className="font-medium text-gray-700 text-xs">{proc.phase}</span>
                </div>
                <span className="text-gray-500 text-xs flex-1">{proc.description}</span>
              </div>
            ))}
          </div>

          {/* Work orders */}
          {day.work_orders?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <p className="text-xs text-gray-400 mb-1">Materials to generate:</p>
              <div className="flex gap-2 flex-wrap">
                {day.work_orders.map((wo, i) => (
                  <span key={i} className="text-xs px-2 py-1 rounded-lg bg-orange-50 text-orange-700 border border-orange-200">
                    {wo.output_template_id} ({wo.question_count}q)
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
