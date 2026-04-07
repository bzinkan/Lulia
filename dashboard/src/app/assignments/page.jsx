'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { PlusCircle, ChevronLeft, ChevronRight, Calendar, FileText, Inbox } from 'lucide-react';
import { apiFetch } from '@/lib/api';

function getMonday(d) {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(date.setDate(diff));
}

export default function AssignmentsPage() {
  const [view, setView] = useState('class');
  const [classes, setClasses] = useState([]);
  const [activeClass, setActiveClass] = useState(null);
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));
  const [weekData, setWeekData] = useState(null);
  const [inboxCount, setInboxCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/manager/classes').then(d => { setClasses(d.classes || []); if (d.classes?.length) setActiveClass(d.classes[0]); }),
      apiFetch('/api/v1/manager/grading-inbox/count').then(d => setInboxCount(d.count || 0)),
    ]).catch(console.error).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!activeClass) return;
    const dateStr = weekStart.toISOString().split('T')[0];
    apiFetch(`/api/v1/manager/classes/${activeClass.class_id}/week?date=${dateStr}`)
      .then(setWeekData)
      .catch(console.error);
  }, [activeClass, weekStart]);

  function shiftWeek(dir) { setWeekStart(d => { const n = new Date(d); n.setDate(n.getDate() + dir * 7); return n; }); }
  const weekEnd = new Date(weekStart); weekEnd.setDate(weekEnd.getDate() + 4);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Assignments</h1>
        </div>
        <div className="flex gap-2">
          <Link href="/assignments/inbox" className="relative bg-white border border-gray-200 text-gray-700 px-3 py-2 rounded-xl text-sm font-medium flex items-center gap-2 hover:bg-gray-50">
            <Inbox className="w-4 h-4" /> Inbox
            {inboxCount > 0 && <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-bold">{inboxCount}</span>}
          </Link>
          <Link href="/assignments/new" className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2">
            <PlusCircle className="w-4 h-4" /> New Assignment
          </Link>
        </div>
      </div>

      {/* View toggle + Class tabs */}
      <div className="bg-white rounded-[14px] p-3 mb-4" style={{ border: '1px solid #E7E5E4' }}>
        <div className="flex items-center justify-between mb-3">
          {/* Class tabs */}
          <div className="flex gap-1 overflow-x-auto">
            {classes.map(c => (
              <button key={c.class_id} onClick={() => setActiveClass(c)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  activeClass?.class_id === c.class_id ? 'bg-orange-500 text-white' : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                }`}>
                {c.name} <span className="opacity-70">({c.assignment_count})</span>
              </button>
            ))}
          </div>
          {/* Week navigator */}
          <div className="flex items-center gap-2 ml-4">
            <button onClick={() => shiftWeek(-1)} className="p-1 rounded hover:bg-gray-100 text-gray-400"><ChevronLeft className="w-4 h-4" /></button>
            <span className="text-xs text-gray-600 whitespace-nowrap">
              {weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – {weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
            <button onClick={() => shiftWeek(1)} className="p-1 rounded hover:bg-gray-100 text-gray-400"><ChevronRight className="w-4 h-4" /></button>
          </div>
        </div>

        {/* Week grid */}
        {weekData && (
          <div className="grid grid-cols-5 gap-2">
            {['mon', 'tue', 'wed', 'thu', 'fri'].map(day => {
              const dayData = weekData.days?.[day] || { date: '', assignments: [] };
              return (
                <div key={day} className="min-h-[120px]">
                  <div className="text-[10px] uppercase tracking-wider text-gray-400 font-medium mb-1 text-center">
                    {day} <span className="text-gray-300">{dayData.date?.slice(5)}</span>
                  </div>
                  <div className="space-y-1">
                    {dayData.assignments.map(a => (
                      <Link key={a.assignment_id} href={`/assignments/${a.assignment_id}`}
                        className="block p-2 bg-white rounded-lg border border-gray-100 hover:border-orange-200 hover:bg-orange-50/30 transition-colors">
                        <div className="flex items-center gap-1">
                          <FileText className="w-3 h-3 text-orange-400" />
                          <span className="text-[11px] text-gray-800 truncate">{a.title?.slice(0, 25)}</span>
                        </div>
                        <div className="flex justify-between mt-1">
                          <span className="text-[9px] text-gray-400">{a.output_template_id}</span>
                          {a.submissions > 0 && <span className="text-[9px] text-orange-500">{a.submissions} sub</span>}
                        </div>
                      </Link>
                    ))}
                    {dayData.assignments.length === 0 && (
                      <div className="text-center py-4">
                        <Link href="/assignments/new" className="text-[10px] text-gray-300 hover:text-orange-400">+ Add</Link>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!weekData && !loading && classes.length === 0 && (
          <div className="text-center py-8">
            <FileText className="w-10 h-10 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No classes yet. Create a class to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
}
