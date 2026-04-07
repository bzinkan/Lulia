'use client';
import { useEffect, useState } from 'react';
import { Users, Plus, BookOpen, BarChart3 } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function ClassesPage() {
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/api/v1/manager/classes')
      .then(d => setClasses(d.classes || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Classes</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your classes and view stats</p>
        </div>
      </div>

      {loading ? (
        <div className="animate-pulse grid grid-cols-2 gap-4">{[1,2].map(i => <div key={i} className="h-32 bg-white/50 rounded-[14px]" />)}</div>
      ) : classes.length === 0 ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <Users className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium" style={{ fontFamily: "'DM Serif Display', serif" }}>No classes yet</h3>
          <p className="text-sm text-gray-500">Classes are created when you generate your first assignment</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {classes.map(c => (
            <div key={c.class_id} className="bg-white rounded-[14px] p-5" style={{ border: '1px solid #E7E5E4' }}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-base font-semibold text-gray-800" style={{ fontFamily: "'DM Serif Display', serif" }}>{c.name}</h3>
                  <p className="text-xs text-gray-400">Grade {c.grade_level} · {c.subject}{c.period ? ` · Period ${c.period}` : ''}</p>
                </div>
                {c.pending_review > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium">{c.pending_review} to review</span>
                )}
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <BookOpen className="w-4 h-4 text-orange-400 mx-auto mb-1" />
                  <p className="text-lg font-bold text-gray-800">{c.assignment_count}</p>
                  <p className="text-[9px] text-gray-400">Assignments</p>
                </div>
                <div className="text-center">
                  <BarChart3 className="w-4 h-4 text-green-400 mx-auto mb-1" />
                  <p className="text-lg font-bold text-gray-800">—</p>
                  <p className="text-[9px] text-gray-400">Avg Mastery</p>
                </div>
                <div className="text-center">
                  <Users className="w-4 h-4 text-blue-400 mx-auto mb-1" />
                  <p className="text-lg font-bold text-gray-800">—</p>
                  <p className="text-[9px] text-gray-400">Students</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
