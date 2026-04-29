'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { BookOpen, CheckCircle, Copy, Eye, Filter, Loader2, Search, XCircle } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';

const FILTER_DEFAULTS = {
  grade_level: '',
  subject: '',
  course: '',
  activity_type: '',
  search: '',
};

function activityTypeLabel(value) {
  return String(value || '')
    .split('_')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function standardCodes(activity) {
  return (activity.standards || [])
    .map(std => (typeof std === 'string' ? std : std?.code))
    .filter(Boolean)
    .slice(0, 3);
}

export default function PrebuiltActivitiesPage() {
  const { activeClassId, activeClass } = useClassContext();
  const [filters, setFilters] = useState(FILTER_DEFAULTS);
  const [activities, setActivities] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [usingActivity, setUsingActivity] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const query = useMemo(() => {
    const params = new URLSearchParams({ status: 'published', limit: '60' });
    ['grade_level', 'subject', 'course', 'activity_type'].forEach(key => {
      if (filters[key]) params.set(key, filters[key]);
    });
    if (filters.search.trim()) params.set('standard_code', filters.search.trim());
    return params.toString();
  }, [filters]);

  const loadActivities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/prebuilt-activities?${query}`);
      setActivities(res.activities || []);
      setTotal(res.total || 0);
      setSelected(current => current || (res.activities || [])[0] || null);
    } catch (e) {
      setError(e.message || 'Could not load prebuilt activities.');
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    loadActivities();
  }, [loadActivities]);

  useEffect(() => {
    if (!selected?.activity_id) {
      setPreviewHtml('');
      return;
    }
    let active = true;
    async function loadPreview() {
      setPreviewLoading(true);
      setError(null);
      try {
        const res = await apiFetch(`/api/v1/prebuilt-activities/${selected.activity_id}/preview`, {
          method: 'POST',
        });
        if (active) setPreviewHtml(res.html || '');
      } catch (e) {
        if (active) setError(e.message || 'Could not render preview.');
      } finally {
        if (active) setPreviewLoading(false);
      }
    }
    loadPreview();
    return () => {
      active = false;
    };
  }, [selected?.activity_id]);

  const courses = useMemo(() => {
    const values = new Set(activities.map(item => item.course).filter(Boolean));
    return Array.from(values).sort();
  }, [activities]);

  async function useActivity(activity) {
    setUsingActivity(true);
    setMessage(null);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/prebuilt-activities/${activity.activity_id}/use`, {
        method: 'POST',
        body: JSON.stringify({
          class_id: activeClassId,
          customizations: {},
        }),
      });
      setMessage({
        type: 'success',
        text: `Copied to your activities. Access code: ${res.access_code}`,
      });
    } catch (e) {
      setError(e.message || 'Could not use this activity.');
    } finally {
      setUsingActivity(false);
    }
  }

  return (
    <div className="max-w-[1400px] mx-auto">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-5">
        <div className="flex items-center gap-3">
          <div
            className="w-12 h-12 rounded-[14px] flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, var(--sage), var(--coral))',
              boxShadow: '0 4px 14px rgba(107,160,138,0.28)',
            }}
          >
            <BookOpen className="w-6 h-6 text-white" strokeWidth={2.4} />
          </div>
          <div>
            <h1 className="font-serif text-[28px] leading-tight" style={{ color: 'var(--text-dark)' }}>
              Prebuilt Activities
            </h1>
            <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
              Browse, preview, and copy standards-aligned interactives into your class.
            </p>
          </div>
        </div>
        {activeClass && (
          <div
            className="px-3 py-2 rounded-xl text-[12px]"
            style={{ background: 'var(--warm-card)', border: '1px solid var(--border)', color: 'var(--text-mid)' }}
          >
            Using for <strong style={{ color: 'var(--text-dark)' }}>{activeClass.name}</strong>
          </div>
        )}
      </div>

      <div
        className="rounded-card p-4 mb-4"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4" style={{ color: 'var(--sage)' }} />
          <span className="text-[12px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
            Filters
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <select
            value={filters.grade_level}
            onChange={e => setFilters(f => ({ ...f, grade_level: e.target.value }))}
            className="px-3 py-2 rounded-xl text-[13px]"
            style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
          >
            <option value="">All grades</option>
            <option value="7">Grade 7</option>
            <option value="9">Grade 9</option>
          </select>
          <select
            value={filters.subject}
            onChange={e => setFilters(f => ({ ...f, subject: e.target.value }))}
            className="px-3 py-2 rounded-xl text-[13px]"
            style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
          >
            <option value="">All subjects</option>
            <option value="Science">Science</option>
            <option value="Math">Math</option>
            <option value="ELA">ELA</option>
            <option value="Social Studies">Social Studies</option>
          </select>
          <select
            value={filters.course}
            onChange={e => setFilters(f => ({ ...f, course: e.target.value }))}
            className="px-3 py-2 rounded-xl text-[13px]"
            style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
          >
            <option value="">All courses</option>
            {courses.map(course => (
              <option key={course} value={course}>{course}</option>
            ))}
          </select>
          <select
            value={filters.activity_type}
            onChange={e => setFilters(f => ({ ...f, activity_type: e.target.value }))}
            className="px-3 py-2 rounded-xl text-[13px]"
            style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
          >
            <option value="">All types</option>
            <option value="visual_study">Visual Study</option>
            <option value="document_study">Document Study</option>
            <option value="model_explorer">Model Explorer</option>
          </select>
          <label
            className="flex items-center gap-2 px-3 py-2 rounded-xl"
            style={{ border: '1px solid var(--border)', background: 'white' }}
          >
            <Search className="w-4 h-4" style={{ color: 'var(--text-light)' }} />
            <input
              value={filters.search}
              onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
              placeholder="Standard"
              className="w-full outline-none text-[13px]"
              style={{ color: 'var(--text-dark)' }}
            />
          </label>
        </div>
      </div>

      {message && (
        <div
          className="flex items-center gap-2 px-4 py-3 rounded-card mb-4"
          style={{ background: 'var(--green-bg, #DCFCE7)', border: '1px solid var(--green-text, #16A34A)', color: 'var(--green-text, #16A34A)' }}
        >
          <CheckCircle className="w-5 h-5" />
          <span className="text-[13px] font-semibold">{message.text}</span>
        </div>
      )}
      {error && (
        <div
          className="flex items-center gap-2 px-4 py-3 rounded-card mb-4"
          style={{ background: 'var(--red-bg, #FEF2F2)', border: '1px solid #EF4444', color: '#EF4444' }}
        >
          <XCircle className="w-5 h-5" />
          <span className="text-[13px] font-semibold">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[420px_minmax(0,1fr)] gap-4">
        <section
          className="rounded-card overflow-hidden"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
        >
          <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
            <span className="font-bold text-[14px]" style={{ color: 'var(--text-dark)' }}>
              Published library
            </span>
            <span className="text-[12px]" style={{ color: 'var(--text-light)' }}>
              {total} activities
            </span>
          </div>
          <div className="max-h-[720px] overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--sage)' }} />
              </div>
            ) : activities.length === 0 ? (
              <div className="p-6 text-center text-[13px]" style={{ color: 'var(--text-mid)' }}>
                No prebuilt activities match these filters.
              </div>
            ) : (
              activities.map(activity => {
                const active = selected?.activity_id === activity.activity_id;
                return (
                  <button
                    key={activity.activity_id}
                    type="button"
                    onClick={() => {
                      setSelected(activity);
                      setMessage(null);
                    }}
                    className="w-full text-left px-4 py-4 transition-colors"
                    style={{
                      borderBottom: '1px solid var(--border)',
                      background: active ? 'rgba(216,108,82,0.10)' : 'transparent',
                    }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-bold text-[14px]" style={{ color: 'var(--text-dark)' }}>
                          {activity.title}
                        </div>
                        <div className="text-[12px] mt-1" style={{ color: 'var(--text-mid)' }}>
                          {activity.course} - Unit {activity.unit_number}, Lesson {activity.lesson_number}
                        </div>
                      </div>
                      <span
                        className="text-[10px] font-bold uppercase px-2 py-1 rounded-full"
                        style={{ color: 'white', background: 'var(--sage)' }}
                      >
                        {activity.estimated_minutes}m
                      </span>
                    </div>
                    <div className="flex gap-2 flex-wrap mt-3">
                      <span className="text-[11px] px-2 py-1 rounded-full" style={{ background: 'var(--cream)', color: 'var(--text-mid)' }}>
                        {activityTypeLabel(activity.activity_type)}
                      </span>
                      {standardCodes(activity).map(code => (
                        <span key={code} className="text-[11px] px-2 py-1 rounded-full" style={{ background: 'white', color: 'var(--text-mid)', border: '1px solid var(--border)' }}>
                          {code}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </section>

        <section
          className="rounded-card overflow-hidden"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
        >
          <div className="px-4 py-3 flex items-center justify-between gap-3 flex-wrap" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2">
              <Eye className="w-4 h-4" style={{ color: 'var(--sage)' }} />
              <span className="font-bold text-[14px]" style={{ color: 'var(--text-dark)' }}>
                Preview
              </span>
            </div>
            {selected && (
              <button
                type="button"
                onClick={() => useActivity(selected)}
                disabled={usingActivity}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-[13px] font-semibold text-white disabled:opacity-60"
                style={{ background: 'var(--coral)' }}
              >
                {usingActivity ? <Loader2 className="w-4 h-4 animate-spin" /> : <Copy className="w-4 h-4" />}
                Use activity
              </button>
            )}
          </div>
          {!selected ? (
            <div className="p-10 text-center text-[13px]" style={{ color: 'var(--text-mid)' }}>
              Select an activity to preview.
            </div>
          ) : previewLoading ? (
            <div className="h-[720px] flex items-center justify-center">
              <Loader2 className="w-7 h-7 animate-spin" style={{ color: 'var(--sage)' }} />
            </div>
          ) : (
            <iframe
              title={`Preview: ${selected.title}`}
              srcDoc={previewHtml}
              className="w-full h-[720px] bg-white"
              style={{ border: 0 }}
            />
          )}
        </section>
      </div>
    </div>
  );
}
